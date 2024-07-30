from copy import copy
from datetime import date, datetime, timedelta
from urllib.parse import urlparse, urlunparse

import pandas as pd
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db.models import Prefetch, Q, Sum
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import LoginForm
from .models import Class, Course, Department, Distribution, Hall, TimeTable, User
from .utils import (
    convert_hall_to_dict,
    distribute_classes_to_halls,
    generate,
    get_courses,
    get_halls,
    handle_uploaded_file,
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
    context = {
        "generated": generated,
        "dates": dates
    }
    if generated:
        date = request.GET.get("date")
        period = request.GET.get("period")
        if date is not None or period is not None:
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
    if request.htmx:
        template_name = "dashboard/pages/allocation.html"
    else:
        template_name = "dashboard/allocation.html"

    return render(request, template_name=template_name)


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
    halls = Hall.objects.all()
    # total_hall_capacity = get_total_no_seats(halls=halls)
    halls = convert_hall_to_dict(halls=halls)
    date = request.POST.get("date")  # noqa: F811
    period = request.POST.get("period")

    timetables = TimeTable.objects.filter(period=period, date=date)

    none_cbe_tt = timetables.exclude(
        course__exam_type__in=["NAN", "CBE"])
    res = distribute_classes_to_halls(
        timetables=none_cbe_tt, halls=halls)
    save_to_db(res, date, period)

    return redirect("distribution")

# ----------------------------
# Upload Views
# ----------------------------


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
                "class_x": halls["X AXIS"][key],
                "class_y": halls["Y AXIS"][key],
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
