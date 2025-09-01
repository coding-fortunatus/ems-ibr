from multiprocessing import context
import random
from datetime import datetime, timedelta
from urllib.parse import urlparse, urlunparse
import io
import zipfile

import pandas as pd
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db.models import Q, Sum, Count
from django.http import HttpRequest, HttpResponse
from django.conf import settings
from django.shortcuts import get_object_or_404, redirect, render, reverse
from django.views.decorators.http import require_POST
from docx import Document
from docx.shared import Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
import os

from .models import Class, Course, Department, Distribution, Hall, TimeTable, User, SeatArrangement, DistributionItem, Student
from .utils import (
    convert_hall_to_dict,
    distribute_classes_to_halls,
    generate,
    get_courses,
    get_halls,
    get_student_number,
    handle_uploaded_file,
    print_seating_arrangement,
    save_to_db,
    split_course,
)


def back_view(request):
    # Get the origin uri
    original_uri = request.META.get('HTTP_REFERER')
    parsed_uri = urlparse(original_uri)

    # Clean up (remove delimiters and empty strings)
    path_parts = parsed_uri.path.split('/')
    path_parts = [path for path in path_parts if path != ""]
    value = path_parts.pop(-1)

    # Construct the referer uri
    new_path_parts = [part for part in path_parts if part != value]
    parsed_uri = parsed_uri._replace(path='/'.join(new_path_parts))

    referer = urlunparse(parsed_uri)

    # redirect to the referer uri
    if referer:
        return redirect(referer)
    else:
        return redirect('dashboard/')


def admin_required(view_func):
    decorated_view_func = user_passes_test(
        lambda user: user.is_staff)(view_func)
    return decorated_view_func


def index(request):
    return render(request, template_name="site/index.html")


def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")
        user = authenticate(request, username=email, password=password)
        if user is not None:
            login(request, user)
            return redirect("dashboard")
        messages.error(request, "Invalid email or password.")
        return redirect("dashboard")

    return render(
        request,
        template_name="site/login.html",
    )


@login_required(login_url="login")
def logout_view(request):
    logout(request)
    return redirect("login")


@login_required(login_url="login")
def dashboard(request):
    departments = Department.objects.all().count()
    halls = Hall.objects.all().count()
    courses = Course.objects.all().count()
    students = Class.objects.aggregate(total_size=Sum('size'))['total_size']

    context = {
        "departments_count": departments,
        "halls_count": halls,
        "courses_count": courses,
        "students": students,
    }
    if request.htmx:
        template_name = "dashboard/pages/dashboard.html"
    else:
        template_name = "dashboard/index.html"

    return render(request, template_name=template_name, context=context)


@login_required(login_url="login")
def departments(request):
    departments_list = Department.objects.all().order_by("id")
    query = request.GET.get("query")
    if query:
        departments_list = departments_list.filter(
            Q(name__icontains=query) | Q(slug__icontains=query)
        )

    paginator = Paginator(departments_list, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    context = {"departments": page_obj}
    if request.htmx:
        template_name = "dashboard/pages/departments.html"
    else:
        template_name = "dashboard/departments.html"

    return render(request, template_name=template_name, context=context)


@login_required(login_url="login")
def get_department(request, slug):
    department = get_object_or_404(Department, slug=slug)
    classes = Class.objects.filter(department=department)
    context = {"department": department, "classes": classes}
    if request.htmx:
        template_name = "dashboard/pages/single-department.html"
    else:
        template_name = "dashboard/single-department.html"

    return render(request, template_name=template_name, context=context)


@login_required(login_url="login")
def get_courses_view(request):
    course_list = Course.objects.all().order_by("id")
    query = request.GET.get("query")
    if query:
        course_list = course_list.filter(
            Q(name__icontains=query) | Q(code__icontains=query)
        )

    paginator = Paginator(course_list, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    context = {"courses": page_obj}
    if request.htmx:
        template_name = "dashboard/pages/courses.html"
    else:
        template_name = "dashboard/courses.html"

    return render(request, template_name=template_name, context=context)


@login_required(login_url="login")
@admin_required
def get_students(request):
    students = Student.objects.all().order_by("id")
    query = request.GET.get("query")
    if query:
        students = students.filter(
            Q(first_name__icontains=query) | Q(
                last_name__icontains=query) | Q(matric_no__icontains=query) | Q(email__icontains=query) | Q(phone__icontains=query)
        )

    paginator = Paginator(students, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    context = {"students": page_obj}
    if request.htmx:
        template_name = "dashboard/pages/students.html"
    else:
        template_name = "dashboard/students.html"

    return render(request, template_name=template_name, context=context)


@login_required(login_url="login")
def get_class_course(request, slug, id):
    cls = get_object_or_404(Class, department__slug=slug, id=id)
    context = {"class": cls, "courses": cls.courses.all()}
    if request.htmx:
        template_name = "dashboard/pages/class.html"
    else:
        template_name = "dashboard/class.html"

    return render(request, template_name=template_name, context=context)


@login_required(login_url="login")
@admin_required
def halls(request):
    halls_list = Hall.objects.all()
    paginator = Paginator(halls_list, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    context = {"halls": page_obj}
    if request.htmx:
        template_name = "dashboard/pages/halls.html"
    else:
        template_name = "dashboard/halls.html"

    return render(request, template_name=template_name, context=context)


@login_required(login_url="login")
def timetable(request: HttpRequest) -> HttpResponse:
    generated = TimeTable.objects.exists()
    context = {
        "generated": generated
    }
    if generated:
        dates = TimeTable.objects.values_list(
            "date", flat=True).distinct().order_by("date")
        date = request.GET.get("date")
        period = request.GET.get("period")
        if date is not None or period is not None:
            timetables = TimeTable.objects.filter(date=date, period=period)
        else:
            timetables = TimeTable.objects.filter(date=dates[0], period="AM")
        if request.user.is_staff is False:
            timetables = timetables.filter(
                class_obj__department=request.user.department)
        context["dates"] = dates
        context["timetables"] = timetables

    if request.htmx:
        template_name = "dashboard/pages/timetable.html"
    else:
        template_name = "dashboard/timetable.html"

    return render(request, template_name=template_name, context=context)


@login_required(login_url="login")
@admin_required
def distribution(request):
    generated = Distribution.objects.exists()
    dates = TimeTable.objects.values_list(
        "date", flat=True).distinct().order_by("date")
    date = request.GET.get("date")
    period = request.GET.get("period")
    context = {
        "generated": generated,
        "dates": dates,
        "date": date,
        "period": period
    }
    if generated:

        if date and period:
            distributions = Distribution.objects.filter(
                date=date, period=period)
        else:
            distributions = Distribution.objects.filter(
                date=dates[0], period="AM")
        context["distributions"] = distributions

    if request.htmx:
        template_name = "dashboard/pages/distribution.html"
    else:
        template_name = "dashboard/distribution.html"

    return render(request, template_name=template_name, context=context)


@login_required(login_url="login")
@admin_required
def allocation(request):
    generated = SeatArrangement.objects.exists()
    dates = TimeTable.objects.values_list(
        "date", flat=True).distinct().order_by("date")
    date = request.GET.get("date")
    period = request.GET.get("period")
    hall_id = request.GET.get("hall")
    
    context = {
        "generated": generated,
        "dates": dates,
        "date": date,
        "period": period,
        "hall_id": hall_id
    }
    
    if generated:
        # Determine which date and period to use
        if date and period:  # Check if both date and period are not empty
            try:
                # Validate date format
                from datetime import datetime
                datetime.strptime(date, "%Y-%m-%d")
                arrangements = SeatArrangement.objects.filter(
                    date=date, period=period)
            except (ValueError, TypeError):
                # If date is invalid, use default
                arrangements = SeatArrangement.objects.filter(
                    date=dates[0], period="AM"
                )
                date = dates[0]
                period = "AM"
        else:
            arrangements = SeatArrangement.objects.filter(
                date=dates[0], period="AM"
            )
            date = dates[0]
            period = "AM"
        
        hall_arrangements = arrangements.values('hall__name', 'hall__id', 'date', 'period').annotate(
            placed=Count('id', filter=Q(seat_number__isnull=False)),
            not_placed=Count('id', filter=Q(seat_number__isnull=True))
        )
        context["arrangements"] = hall_arrangements
    
    if request.htmx:
        template_name = "dashboard/pages/allocation.html"
    else:
        template_name = "dashboard/allocation.html"

    return render(request, template_name=template_name, context=context)


@login_required(login_url="login")
@admin_required
def hall_allocation(request):
    """
    View for detailed hall allocation with visual seat layout
    """
    generated = SeatArrangement.objects.exists()
    dates = TimeTable.objects.values_list(
        "date", flat=True).distinct().order_by("date")
    date = request.GET.get("date")
    period = request.GET.get("period")
    hall_id = request.GET.get("hall_id")
    
    if not hall_id:
        messages.error(request, "Hall ID is required for detailed view.")
        return redirect("allocation")
    
    context = {
        "generated": generated,
        "dates": dates,
        "date": date,
        "period": period,
        "hall_id": hall_id
    }
    
    if generated:
        # Determine which date and period to use
        if date and period:
            try:
                from datetime import datetime
                datetime.strptime(date, "%Y-%m-%d")
                arrangements = SeatArrangement.objects.filter(
                    date=date, period=period, hall_id=hall_id)
            except (ValueError, TypeError):
                arrangements = SeatArrangement.objects.filter(
                    date=dates[0], period="AM", hall_id=hall_id
                )
                date = dates[0]
                period = "AM"
        else:
            arrangements = SeatArrangement.objects.filter(
                date=dates[0], period="AM", hall_id=hall_id
            )
            date = dates[0]
            period = "AM"
        
        # Get detailed seat arrangement for the specific hall
        hall_details = arrangements.select_related(
            'student', 'course', 'cls', 'hall'
        ).order_by('seat_number')
        
        # Separate placed and unplaced students
        placed_students = hall_details.filter(seat_number__isnull=False)
        unplaced_students = hall_details.filter(seat_number__isnull=True)
        
        # Get hall info for seating grid
        if hall_details.exists():
            hall = hall_details.first().hall
            
            # Create a 2D grid for visual representation
            seat_grid = []
            if hall.rows and hall.columns:
                # Initialize empty grid
                for row in range(hall.rows):
                    seat_row = []
                    for col in range(hall.columns):
                        seat_number = row * hall.columns + col + 1
                        seat_row.append({
                            'seat_number': seat_number,
                            'student': None,
                            'course': None,
                            'is_occupied': False
                        })
                    seat_grid.append(seat_row)
                
                # Fill grid with placed students
                for student in placed_students:
                    if student.seat_number:
                        # Convert seat number to row, col (1-indexed to 0-indexed)
                        seat_num = student.seat_number - 1
                        row = seat_num // hall.columns
                        col = seat_num % hall.columns
                        
                        if 0 <= row < hall.rows and 0 <= col < hall.columns:
                            seat_grid[row][col].update({
                                'student': student.student,
                                'course': student.course,
                                'is_occupied': True,
                                'student_matric_no': getattr(student, 'student_matric_no', ''),
                                'cls': student.cls
                            })
            
            context.update({
                "hall_details": hall_details,
                "placed_students": placed_students,
                "unplaced_students": unplaced_students,
                "selected_hall": hall,
                "hall_capacity": hall.rows * hall.columns if hall.rows and hall.columns else 0,
                "seat_grid": seat_grid
            })
    
    if request.htmx:
        template_name = "dashboard/pages/hall-allocation.html"
    else:
        template_name = "dashboard/hall-allocation.html"

    return render(request, template_name=template_name, context=context)


@login_required(login_url="login")
@admin_required
def generate_attendance_sheets(request):
    """Generate attendance sheets for all courses in a specific hall"""
    date = request.GET.get("date")
    period = request.GET.get("period")
    hall_id = request.GET.get("hall_id")
    
    if not all([date, period, hall_id]):
        messages.error(request, "Date, period, and hall must be specified.")
        return redirect("hall-allocation")
    print("Yay")
    
    try:
        # Validate date format
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        messages.error(request, "Invalid date format.")
        return redirect("allocation")
    
    # Get arrangements for the specific hall, date, and period
    arrangements = SeatArrangement.objects.filter(
        date=date, period=period, hall_id=hall_id
    ).select_related('student', 'course', 'cls', 'hall').order_by('course__name', 'student__matric_no')
    
    if not arrangements.exists():
        messages.error(request, "No seat arrangements found for the specified criteria.")
        return redirect("allocation")
    
    hall = arrangements.first().hall
    
    # Group students by course
    courses_data = {}
    for arrangement in arrangements:
        if arrangement.seat_number:  # Only placed students
            course_key = f"{arrangement.course.name} ({arrangement.course.code})"
            if course_key not in courses_data:
                courses_data[course_key] = {
                    'course': arrangement.course,
                    'cls': arrangement.cls,
                    'students': []
                }
            courses_data[course_key]['students'].append(arrangement)
    
    if not courses_data:
        messages.error(request, "No placed students found for attendance sheets.")
        return redirect("allocation")
    
    # Create a zip file containing all attendance sheets
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for course_key, course_data in courses_data.items():
            # Create Word document for each course
            doc = Document()
            
            # Add school logo
            logo_paragraph = doc.add_paragraph()
            logo_paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
            
            # Try to add the actual logo image
            logo_path = os.path.join(settings.BASE_DIR, 'static', 'assets', 'images', 'logo.png')
            if os.path.exists(logo_path):
                try:
                    # Add the logo image to the document
                    logo_run = logo_paragraph.runs[0] if logo_paragraph.runs else logo_paragraph.add_run()
                    logo_run.add_picture(logo_path, width=Inches(1.0))

                except Exception:
                    # Fallback to text if image insertion fails
                    logo_run = logo_paragraph.add_run("[SCHOOL LOGO]")
                    logo_run.bold = True
            else:
                # Fallback if logo file doesn't exist
                logo_run = logo_paragraph.add_run("[SCHOOL LOGO]")
                logo_run.bold = True
            
            # Add course information header
            course_header = doc.add_paragraph()
            course_header.alignment = WD_ALIGN_PARAGRAPH.LEFT
            course_run = course_header.add_run(f"COURSE TITLE: {course_data['course'].name.upper()}")
            course_run.bold = True
            course_run.add_break()
            code_run = course_header.add_run(f"COURSE CODE: {course_data['course'].code}")
            code_run.bold = True
            
            # Add exam details
            exam_details = doc.add_paragraph()
            exam_details.alignment = WD_ALIGN_PARAGRAPH.LEFT
            hall_run = exam_details.add_run(f"EXAM HALL: {hall.name}")
            hall_run.bold = True
            hall_run.add_break()

            date_run = exam_details.add_run(f"DATE: {datetime.strptime(date, '%Y-%m-%d').strftime('%d %B, %Y')}")
            date_run.bold = True
            
            # Add level and period
            level_period = doc.add_paragraph()
            level_period.alignment = WD_ALIGN_PARAGRAPH.LEFT
            level_run = level_period.add_run(f"LEVEL/CLASS: {course_data['cls'].name}")
            level_run.bold = True
            level_run.add_break()
            period_run = level_period.add_run(f"PERIOD OF EXAM: {period}")
            period_run.bold = True


            # Add attendance sheet header
            attendance_header = doc.add_paragraph()
            attendance_header.alignment = WD_ALIGN_PARAGRAPH.CENTER
            attendance_run = attendance_header.add_run("ATTENDANCE SHEET")
            attendance_run.bold = True
            
            # Add spacing
            doc.add_paragraph()
            doc.add_paragraph()
            
            # Create attendance table
            table = doc.add_table(rows=1, cols=7)
            table.style = 'Table Grid'
            table.alignment = WD_TABLE_ALIGNMENT.CENTER
            
            # Add table headers
            hdr_cells = table.rows[0].cells
            headers = ['S/NO', 'MATRIC NO', "STUDENT'S NAME", 'SEAT NO', 'SCRIPT NO', 'SIGN IN', 'SIGN OUT']
            for i, header in enumerate(headers):
                hdr_cells[i].text = header
                hdr_cells[i].paragraphs[0].runs[0].bold = True
            
            # Add student data
            for idx, student in enumerate(course_data['students'], 1):
                row_cells = table.add_row().cells
                row_cells[0].text = str(idx)
                row_cells[1].text = student.student.matric_no
                row_cells[2].text = f"{student.student.first_name} {student.student.last_name}".upper()
                row_cells[3].text = str(student.seat_number) if student.seat_number else ''
                # Leave script no, sign in, sign out empty for manual filling
            
            # Add extra blank rows (20-25 as requested)
            for i in range(25):
                row_cells = table.add_row().cells
                if i < 3:  # First 3 extra rows have numbers
                    row_cells[0].text = str(len(course_data['students']) + i + 1)
            
            # Add spacing
            doc.add_paragraph()
            doc.add_paragraph()
            
            # Add footer information
            footer_info = doc.add_paragraph()
            footer_info.alignment = WD_ALIGN_PARAGRAPH.CENTER
            total_run = footer_info.add_run("TOTAL NUMBER OF STUDENTS……………………………TOTAL NUMBER OF SCRIPTS…………………….")
            total_run.bold = True
            
            invigilator_info = doc.add_paragraph()
            invigilator_info.alignment = WD_ALIGN_PARAGRAPH.CENTER
            invig_run = invigilator_info.add_run("NAME OF INVIGILATOR SUBMITING SCRIPTS………………………………………………. SIGN…………....")
            invig_run.bold = True
            
            committee_info = doc.add_paragraph()
            committee_info.alignment = WD_ALIGN_PARAGRAPH.CENTER
            committee_run = committee_info.add_run("NAME OF EXAM COMMITTEE MEMBER RECEIVING SCRIPTS…………………………………………………")
            committee_run.bold = True
            
            signature_info = doc.add_paragraph()
            signature_info.alignment = WD_ALIGN_PARAGRAPH.CENTER
            sig_run = signature_info.add_run("SIGNATURE……………………………….                                        DATE…………………………………...")
            sig_run.bold = True
            
            # Add range information
            if course_data['students']:
                last_matric = course_data['students'][-1].student.matric_no.split('/')[-1]
                range_info = doc.add_paragraph()
                range_info.alignment = WD_ALIGN_PARAGRAPH.CENTER
                range_run = range_info.add_run(f"RANGE: {last_matric}")
                range_run.bold = True
            
            # Save document to buffer
            doc_buffer = io.BytesIO()
            doc.save(doc_buffer)
            doc_buffer.seek(0)
            
            # Add to zip file
            filename = f"Attendance_{course_data['course'].code}_{hall.name}_{date}_{period}.docx"
            zip_file.writestr(filename, doc_buffer.getvalue())
    
    # Prepare response
    zip_buffer.seek(0)
    response = HttpResponse(zip_buffer.getvalue(), content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="Attendance_Sheets_{hall.name}_{date}_{period}.zip"'
    
    return response


@login_required(login_url="login")
@admin_required
def manage_users(request):
    users = User.objects.all()
    department_list = Department.objects.all()
    query = request.GET.get("query")
    if query:
        users = users.filter(
            Q(first_name__icontains=query) | Q(last_name__icontains=query)
        )

    paginator = Paginator(users, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    context = {"users": page_obj, "departments": department_list}

    if request.htmx:
        template_name = "dashboard/pages/manage-users.html"
    else:
        template_name = "dashboard/manage-users.html"

    return render(request, template_name=template_name, context=context)


@require_POST
@login_required(login_url="login")
@admin_required
def add_user(request):
    first_name = request.POST.get("first_name")
    last_name = request.POST.get("last_name")
    email = request.POST.get("email")
    department_slug = request.POST.get("department")
    password = request.POST.get("password")
    password_confirm = request.POST.get("password-confirm")

    if password != password_confirm:
        return render(
            request,
            template_name="dashboard/partials/alert-error.html",
            context={"message": "Passwords do not match"},
        )
    if not Department.objects.filter(slug=department_slug).exists():
        return render(
            request,
            template_name="dashboard/partials/alert-error.html",
            context={
                "message": f"Department with code {department_slug} does not exists"
            },
        )
    if User.objects.filter(email=email).exists():
        return render(
            request,
            template_name="dashboard/partials/alert-error.html",
            context={"message": "Email already exists"},
        )

    user = User.objects.create_user(
        first_name=first_name,
        last_name=last_name,
        email=email,
        department=get_object_or_404(Department, slug=department_slug),
        password=password,
    )
    user.save()
    return render(
        request,
        template_name="dashboard/partials/alert-success.html",
        context={"message": "User created successfully"},
    )


@login_required(login_url="login")
@admin_required
def reset_system(request: HttpRequest) -> HttpResponse:
    SeatArrangement.objects.all().delete()
    Distribution.objects.all().delete()
    DistributionItem.objects.all().delete()
    TimeTable.objects.all().delete()
    Hall.objects.all().delete()
    Course.objects.all().delete()
    Class.objects.all().delete()

    return redirect("dashboard")


# --------------------------
#  Generate Views
# --------------------------


@require_POST
@login_required(login_url="login")
@admin_required
def generate_timetable(request: HttpRequest) -> HttpResponse:
    startDate = request.POST.get("startDate")
    endDate = request.POST.get("endDate")

    if startDate == "" or endDate == "":
        return render(
            request,
            template_name="dashboard/partials/alert-error.html",
            context={"message": "Please select a start date and end date"},
        )

    startDate = datetime.strptime(startDate, "%Y-%m-%d").date()
    endDate = datetime.strptime(endDate, "%Y-%m-%d").date()

    if startDate > endDate:
        return render(
            request,
            template_name="dashboard/partials/alert-error.html",
            context={"message": "End date must be greater than start date"},
        )

    dates = []
    currentDate = startDate
    while currentDate <= endDate:
        if currentDate.weekday() != 6:  # 6 represents Sunday
            dates.append(currentDate)
        currentDate += timedelta(days=1)

    halls = get_halls()
    courses = get_courses()
    AM_courses, PM_courses = split_course(courses)
    generate(dates, AM_courses, PM_courses, halls)

    return render(
        request,
        template_name="dashboard/partials/alert-success.html",
        context={"message": "Time table generated"},
    )


@require_POST
@login_required(login_url="login")
@admin_required
def generate_distribution(request: HttpRequest) -> HttpResponse:
    date = request.POST.get("date")
    period = request.POST.get("period")
    print(date)
    print(period)
    if not Distribution.objects.filter(date=date, period=period).exists():
        halls = Hall.objects.all()
        halls = convert_hall_to_dict(halls=halls)
        timetables = TimeTable.objects.filter(period=period, date=date)

        none_cbe_tt = timetables.exclude(
            course__exam_type__in=["NAN", "CBE"])
        res = distribute_classes_to_halls(
            timetables=none_cbe_tt, halls=halls)
        save_to_db(res, date, period)

    return redirect(reverse('distribution') + f'?date={date}&period={period}')


@require_POST
@login_required(login_url="login")
@admin_required
def generate_allocation(request: HttpRequest) -> HttpResponse:
    date = request.POST.get("date")
    period = request.POST.get("period")
    if not SeatArrangement.objects.filter(date=date, period=period).exists():
        distributions = Distribution.objects.filter(date=date, period=period)

        for distribution in distributions:
            rows = distribution.hall.rows
            cols = distribution.hall.columns
            students = []
            for item in distribution.items.all():
                course_code = item.schedule.course.code
                class_obj = item.schedule.class_obj
                
                # Get real students from the database for this class and course
                real_students = Student.objects.filter(
                    level=class_obj,
                    department=class_obj.department
                ).order_by('matric_no')[:item.no_of_students]
                
                # If we don't have enough real students, fill with available students from the same department
                if len(real_students) < item.no_of_students:
                    additional_students = Student.objects.filter(
                        department=class_obj.department
                    ).exclude(
                        id__in=[s.id for s in real_students]
                    ).order_by('matric_no')[:item.no_of_students - len(real_students)]
                    real_students = list(real_students) + list(additional_students)
                
                # If still not enough students, create and save new random students
                remaining_count = item.no_of_students - len(real_students)
                created_students = []
                for i in range(remaining_count):
                    matric_no = get_student_number(
                        class_obj.department.slug, class_obj, len(real_students) + i + 1
                    )
                    
                    # Check if student with this matric_no already exists
                    existing_student = Student.objects.filter(matric_no=matric_no).first()
                    if not existing_student:
                        # Create new student
                        new_student = Student.objects.create(
                            first_name=f"Student",
                            last_name=f"{len(real_students) + i + 1:04d}",
                            matric_no=matric_no,
                            email=f"{matric_no.lower().replace('/', '')}@student.edu",
                            department=class_obj.department,
                            level=class_obj,
                            phone="+1234567890"
                        )
                        created_students.append(new_student)
                    else:
                        created_students.append(existing_student)
                
                # Combine all students
                all_students = list(real_students) + created_students
                
                # Add students to the list with their actual data
                for student in all_students:
                    students.append({
                        "student_id": student.id,
                        "name": student.matric_no,
                        "course": course_code,
                        "cls_id": class_obj.id
                    })
                    
            random.seed(0)
            # Ensure the total number of students does not exceed rows * cols
            if len(students) > rows * cols:
                print(
                    f"Error: Too many students for the given hall capacity of {rows * cols} seats.")
            else:
                print("Hall", distribution.hall.name)
                print_seating_arrangement(
                    students, rows, cols, datetime.strptime(date, "%Y-%m-%d").date(), period, distribution.hall.id)
        # Generate the allocation for the distribution
    return redirect(reverse('allocation') + f'?date={date}&period={period}')

# ----------------------------
# Upload Views
# ----------------------------


@require_POST
@login_required(login_url="login")
@admin_required
def upload_courses(request):
    data = request.FILES.get("file")
    courses = pd.read_csv(data)
    courses = courses.to_dict()
    for key in courses["COURSE CODE"]:
        course, created = Course.objects.get_or_create(
            code=courses["COURSE CODE"][key],
            defaults={
                "name": courses["COURSE TITLE"][key],
                "exam_type": courses["EXAM TYPE"][key]
            },
        )
        if created:
            course.save()
    if created:
        return HttpResponse('<div class="alert alert-success">Courses uploaded successfully!</div>')
    else:
        return HttpResponse('<div class="alert alert-danger">Upload error, please try again.</div>')


@require_POST
@login_required(login_url="login")
@admin_required
def upload_classes(request, dept_slug):
    department = get_object_or_404(Department, slug=dept_slug)
    data = request.FILES.get("file")
    dept = pd.read_csv(data)
    dept = dept.to_dict()
    for key in dept["Name"]:
        cls, created = Class.objects.get_or_create(
            name=dept["Name"][key],
            department=department,
            defaults={"size": dept["Size"][key]},
        )
        if created:
            cls.save()
    return redirect("get_department", department.slug)


@require_POST
@require_POST
@login_required(login_url="login")
@admin_required
def upload_departments(request):
    if request.method == "POST":
        data = request.FILES.get("file")
        dept = pd.read_csv(data)
        dept = dept.to_dict()
        for key in dept["Code"]:
            department, created = Department.objects.get_or_create(
                slug=dept["Code"][key],
                defaults={"name": dept["Name"][key]},
            )
            if created:
                department.save()
        return redirect("department")


@require_POST
@login_required(login_url="login")
@admin_required
def upload_class_courses(request, id):
    cls = get_object_or_404(Class, id=id)
    all_courses = Course.objects.all()
    data = request.FILES.get("file")
    courses = pd.read_csv(data).to_dict()
    for key in courses["COURSE CODE"]:
        course, created = Course.objects.get_or_create(
            code=courses["COURSE CODE"][key],
            defaults={
                "name": courses["COURSE TITLE"][key],
                "exam_type": courses["EXAM TYPE"][key],
            },
        )
        if created:
            course.save()
        cls.courses.add(course)
        cls.save()
    return render(
        request,
        template_name="dashboard/partials/alert-success.html",
        context={"message": "Courses uploaded successfully"},
    )


@require_POST
@login_required(login_url="login")
@admin_required
def upload_class_students(request, id):
    cls = get_object_or_404(Class, id=id)
    data = request.FILES.get("file")
    students = pd.read_csv(data).to_dict()
    for key in students["MATRIC NUMBER"]:
        student, created = Student.objects.get_or_create(
            matric_number=students["MATRIC NUMBER"][key],
            defaults={
                "firstname": students["FIRSTNAME"][key],
                "lastname": students["LASTNAME"][key],
                "email": students["EMAIL"][key],
                "phone": students["PHONE"][key],
                "department": cls.department.id,
                "level": cls.id,
            },
        )
        if created:
            student.save()
        cls.students.add(student)
        cls.save()
    return render(
        request,
        template_name="dashboard/partials/alert-success.html",
        context={"message": "Students uploaded successfully"},
    )


@require_POST
@login_required(login_url="login")
@admin_required
def upload_halls(request):
    data = request.FILES.get("file")
    halls = pd.read_csv(data).to_dict()
    for key in halls["EXAM VENUE"]:
        hall, created = Hall.objects.get_or_create(
            name=halls["EXAM VENUE"][key],
            defaults={
                "capacity": halls["CAPACITY"][key],
                "max_students": halls["MAX STUDENTS"][key],
                "min_courses": halls["MIN COURSES"][key],
                "rows": halls["ROWS"][key],
                "columns": halls["COLS"][key],
            },
        )
        if created:
            hall.save()
    return render(
        request,
        template_name="dashboard/partials/alert-success.html",
        context={"message": "Halls uploaded successfully"},
    )


def bulk_upload(request):
    if request.method == 'POST':
        file = request.FILES['file']
        upload_type = request.POST['upload_type']
        handle_uploaded_file(file, upload_type)
        return render(
            request,
            template_name="dashboard/partials/alert-success.html",
            context={"message": "Halls uploaded successfully"},
        )
    else:
        return render(request, template_name='dashboard/upload.html')
