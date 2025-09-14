import os
import random
import shutil
import zipfile

import pandas as pd  # type: ignore
from django.conf import settings
from django.db.models import Prefetch

from .models import (
    Class,
    Course,
    Department,
    Distribution,
    DistributionItem,
    Hall,
    TimeTable,
    SeatArrangement
)

################################################################################################################################################################

# Get Halls to memory location


def get_halls():
    """To get all Halls into memory location"""
    return [{"id": hall.id, "name": hall.name, "capacity": hall.capacity} for hall in Hall.objects.all()]


# Get courses to memory location
def get_courses():
    """To get courses based on classes object"""
    courses = Course.objects.prefetch_related(
        Prefetch('courses', queryset=Class.objects.select_related('department'))
    ).all()

    return [
        {
            "id": course.id,
            "code": course.code,
            "exam_type": course.exam_type,
            "classes": [
                {
                    "id": cls.id,
                    "name": cls.name,
                    "size": cls.size
                } for cls in course.courses.all()
            ]
        } for course in courses
    ]


# Save timetable to DB
def save_to_timetable_db(schedules):
    """Save schedule into the timetable in DB"""
    timetables = []
    for schedule in schedules:
        for cls in schedule['course']['classes']:
            timetables.append(
                TimeTable(
                    course=Course.objects.get(id=schedule['course']['id']),
                    class_obj=Class.objects.get(id=cls['id']),
                    date=schedule['date'],
                    period=schedule['period']
                )
            )
    TimeTable.objects.bulk_create(timetables)


# Check for the Class type to detect AM or PM courses (ND1, PND1, HND1 = "AM" ND2, PND2, HND2 = "PM") for only PBE courses
def check_course_period(course):
    for item in course['classes']:
        if item['name'].endswith('II') or item['name'].endswith('2'):
            return True
    return False


# Split courses into AM And PM periods respectively bases on exam type
def split_course(courses):
    AM_courses, PM_courses = [], []
    for course in courses:
        if course['exam_type'] == "PBE":
            if check_course_period(course):
                PM_courses.append(course)
            else:
                AM_courses.append(course)
        else:
            AM_courses.append(course)
    return (AM_courses, PM_courses)


# Helper function to check if a class is scheduled on a given date
def is_class_scheduled(course, date, Schedules):
    for cls in course['classes']:
        for schedule in Schedules:
            if schedule["date"] == date and cls in schedule["course"]["classes"]:
                return True
    return False


# Helper function to get total available seats per period
def get_total_seats(Halls):
    return int(sum([Hall["capacity"] * 0.9 for Hall in Halls]))


# Check for CBE Schedule
def check_for_CBE(schedules, date):
    schedules_date = filter(
        lambda schedule: schedule['date'] == date, schedules)
    for schedule in schedules_date:
        if schedule['course']['exam_type'] == "CBE":
            return True
    return False


# Helper function to check if timetable can still be scheduled based on the number of seats remaining
def can_continue(date, seat_remaining, courses, Schedules):
    for course in courses:
        Seat_Required = sum([Class["size"] for Class in course["classes"]])
        if seat_remaining >= Seat_Required and not is_class_scheduled(course, date, Schedules) and not check_for_CBE(Schedules, date):
            return True
    return False


def can_continue_PM(date, seat_remaining, courses, Schedules):
    for course in courses:
        Seat_Required = sum([Class["size"] for Class in course["classes"]])
        if seat_remaining >= Seat_Required and not is_class_scheduled(course, date, Schedules):
            return True
    return False


def filter_courses(date, seat_remaining, courses, schedules):
    eligible_courses = []
    for course in courses:
        seat_required = sum(cls["size"] for cls in course["classes"])
        if seat_remaining >= seat_required and not is_class_scheduled(course, date, schedules):
            eligible_courses.append(course)
    return eligible_courses


# Get the next valid course to schedule
def get_next_course(date, seat_remaining, courses, Schedules):
    courses_to_select = filter_courses(
        date, seat_remaining, courses, Schedules)
    return random.choice(courses_to_select)


# Function to generate the timetable and save it to the DB
def generate(dates, courses_AM, courses_PM, Halls):
    # Initialize schedules list
    Schedules = []
    # Loop through the dates
    for Date in dates:
        Total_Seats_AM = get_total_seats(Halls)
        Total_Seats_PM = get_total_seats(Halls)

        AM_scheduling = True
        # While there are still seats available and courses to add
        while AM_scheduling:
            if not can_continue(Date, Total_Seats_AM, courses_AM, Schedules):
                AM_scheduling = False
            Course = get_next_course(
                Date, Total_Seats_AM, courses_AM, Schedules)
            if Course['exam_type'] == "CBE":
                if not check_for_CBE(Schedules, Date):
                    Schedule = {"course": Course, "date": Date, "period": "AM"}
                    Schedules.append(Schedule)
                    courses_AM.remove(Course)
            else:
                Seat_Required = sum([Class["size"]
                                    for Class in Course["classes"]])
                if Total_Seats_AM >= Seat_Required and not is_class_scheduled(Course, Date, Schedules):
                    Schedule = {"course": Course,
                                "date": Date, "period": "AM"}
                    Schedules.append(Schedule)
                    Total_Seats_AM -= Seat_Required
                    courses_AM.remove(Course)
                    if Total_Seats_AM == 0:
                        AM_scheduling = False
                    if len(filter_courses(Date, Total_Seats_AM, courses_AM, Schedules)) == 0:
                        AM_scheduling = False
                        #  Schedule PM Courses
        PM_scheduling = True
        while PM_scheduling:
            if not can_continue_PM(Date, Total_Seats_PM, courses_PM, Schedules):
                PM_scheduling = False
            else:
                Course = get_next_course(
                    Date, Total_Seats_PM, courses_PM, Schedules)
                Seat_Required = sum([Class["size"]
                                    for Class in Course["classes"]])
                if Total_Seats_PM >= Seat_Required and not is_class_scheduled(Course, Date, Schedules):
                    Schedule = {"course": Course, "date": Date, "period": "PM"}
                    Schedules.append(Schedule)
                    Total_Seats_PM -= Seat_Required
                    courses_PM.remove(Course)
                    if Total_Seats_PM == 0:
                        PM_scheduling = False
                    if len(filter_courses(Date, Total_Seats_PM, courses_PM, Schedules)) == 0:
                        PM_scheduling = False
    # Bulk upload schedules to timetable Db
    save_to_timetable_db(Schedules)


################################################################################################################################################################


def get_total_no_seats(halls):
    sum = 0
    for hall in halls:
        sum += hall.capacity

    return sum


def get_total_no_seats_needed(timetables):
    sum = 0
    for timetable in timetables:
        sum += timetable.class_obj.size
    return sum


def convert_hall_to_dict(halls):
    halls_dict = []
    for hall in halls:
        hall_dict = {
            "id": hall.id,
            "name": hall.name,
            "capacity": hall.capacity,
            "max_students": hall.max_students,
            "min_courses": hall.min_courses,
            "classes": []
        }
        halls_dict.append(hall_dict)
    return halls_dict


def make_schedules(timetables):
    tt = []
    for timetable in timetables:
        tt.append({"id": timetable.id, 'class': timetable.class_obj.name,
                   "course": timetable.course.code, "size": timetable.class_obj.size})
    random.shuffle(tt)
    return tt


def is_course_in_hall(hall, course_code):
    if len(hall["classes"]) == 0:
        return False
    for cls in hall["classes"]:
        if cls["course"] == course_code:
            return True
    return False


def distribute_classes_to_halls(timetables, halls):
    """
    Optimized distribution algorithm that minimizes hall usage while maximizing student placement.
    Uses constraint-aware capacity calculations and intelligent packing strategies.
    """
    class_schedules = make_schedules(timetables=timetables)
    
    # Sort halls by capacity (largest first) for optimal packing
    sorted_halls = sorted(halls, key=lambda h: h["capacity"], reverse=True)
    
    # Sort schedules by size (largest first) for better bin packing
    sorted_schedules = sorted(class_schedules, key=lambda s: s["size"], reverse=True)
    
    results = []
    used_halls = []
    
    # Calculate constraint factor for realistic capacity (reserve space for course separation)
    CONSTRAINT_FACTOR = 0.85  # Use 85% of capacity to account for adjacency constraints
    
    for schedule in sorted_schedules:
        if schedule["size"] == 0:
            continue
            
        placed = False
        
        # First, try to place in already used halls (minimize hall count)
        for hall in used_halls:
            if can_place_in_hall(hall, schedule, CONSTRAINT_FACTOR):
                place_schedule_in_hall(hall, schedule)
                placed = True
                break
        
        # If not placed, try new halls
        if not placed:
            for hall in sorted_halls:
                if hall not in used_halls and can_place_in_hall(hall, schedule, CONSTRAINT_FACTOR):
                    place_schedule_in_hall(hall, schedule)
                    used_halls.append(hall)
                    placed = True
                    break
        
        # If still not placed, use fallback strategy (relaxed constraints)
        if not placed:
            for hall in sorted_halls:
                if hall not in used_halls and can_place_in_hall_relaxed(hall, schedule):
                    place_schedule_in_hall(hall, schedule)
                    used_halls.append(hall)
                    break
    
    # Return only halls that have classes assigned
    for hall in used_halls:
        if len(hall["classes"]) > 0:
            results.append(hall)
    
    return results


def can_place_in_hall(hall, schedule, constraint_factor):
    """
    Check if a schedule can be placed in a hall with constraint-aware capacity.
    """
    # Check course conflict
    if is_course_in_hall(hall, schedule["course"]):
        return False
    
    # Check minimum courses limit
    if len(hall["classes"]) >= hall["min_courses"]:
        return False
    
    # Calculate effective capacity with constraint factor
    effective_capacity = int(hall["capacity"] * constraint_factor)
    
    # Check if schedule fits in effective capacity
    students_to_place = min(hall["max_students"], schedule["size"])
    
    return effective_capacity >= students_to_place


def can_place_in_hall_relaxed(hall, schedule):
    """
    Relaxed placement check for fallback scenarios.
    """
    if is_course_in_hall(hall, schedule["course"]):
        return False
    
    if len(hall["classes"]) >= hall["min_courses"]:
        return False
    
    students_to_place = min(hall["max_students"], schedule["size"])
    return hall["capacity"] >= students_to_place


def place_schedule_in_hall(hall, schedule):
    """
    Place a schedule in a hall and update capacities.
    """
    number_of_students = hall["max_students"]
    if number_of_students >= schedule["size"]:
        number_of_students = schedule["size"]
    
    # If remaining students are less than 5, take all
    if schedule["size"] - number_of_students < 5:
        number_of_students = schedule["size"]
    
    res = {
        "id": schedule["id"], 
        "class": schedule["class"], 
        "course": schedule["course"],
        "student_range": number_of_students
    }
    
    hall["classes"].append(res)
    hall["capacity"] -= number_of_students
    schedule["size"] -= number_of_students


def save_to_db(res, date, period):
    """
    Save distribution results to database with optimization statistics.
    """
    total_halls_used = len(res)
    total_students_distributed = 0
    total_capacity_used = 0
    total_available_capacity = 0
    
    for item in res:
        hall = Hall.objects.get(id=item["id"])
        hall_capacity = hall.capacity
        hall_students = sum(cls["student_range"] for cls in item["classes"])
        
        total_students_distributed += hall_students
        total_capacity_used += hall_students
        total_available_capacity += hall_capacity
        
        distribution = Distribution.objects.create(
            hall=hall, date=date, period=period
        )
        for cls in item["classes"]:
            schedule = TimeTable.objects.get(id=cls["id"])
            dist_item = DistributionItem.objects.create(
                schedule=schedule, no_of_students=cls["student_range"]
            )
            distribution.items.add(dist_item)
            distribution.save()
        distribution.save()
    
    # Print optimization statistics
    utilization_rate = (total_capacity_used / total_available_capacity * 100) if total_available_capacity > 0 else 0
    print(f"\n=== Distribution Optimization Results ===")
    print(f"Halls used: {total_halls_used}")
    print(f"Students distributed: {total_students_distributed}")
    print(f"Total capacity utilization: {utilization_rate:.1f}%")
    print(f"Average students per hall: {total_students_distributed / total_halls_used:.1f}")
    print(f"========================================\n")


def get_distribution_statistics(date, period):
    """
    Get comprehensive statistics for a distribution.
    """
    distributions = Distribution.objects.filter(date=date, period=period)
    
    stats = {
        'total_halls': distributions.count(),
        'total_students': 0,
        'total_capacity': 0,
        'halls_data': []
    }
    
    for dist in distributions:
        hall_students = sum(item.no_of_students for item in dist.items.all())
        hall_capacity = dist.hall.capacity
        hall_utilization = (hall_students / hall_capacity * 100) if hall_capacity > 0 else 0
        
        stats['total_students'] += hall_students
        stats['total_capacity'] += hall_capacity
        
        stats['halls_data'].append({
            'hall_name': dist.hall.name,
            'students': hall_students,
            'capacity': hall_capacity,
            'utilization': hall_utilization,
            'courses': len(set(item.schedule.course.code for item in dist.items.all()))
        })
    
    stats['overall_utilization'] = (stats['total_students'] / stats['total_capacity'] * 100) if stats['total_capacity'] > 0 else 0
    
    return stats


###################################
##### BULK UPLOAD FUNCTION ########
###################################

def handle_uploaded_file(file, upload_type):
    print("File Uploaded Successful")
    temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp_upload')
    print(os.makedirs(temp_dir, exist_ok=True))

    file_path = os.path.join(temp_dir, file.name)
    with open(file_path, 'wb+') as destination:
        for chunk in file.chunks():
            destination.write(chunk)

    with zipfile.ZipFile(file_path, 'r') as zip_ref:
        zip_ref.extractall(temp_dir)

    if upload_type == 'courses':
        process_class_course_files(temp_dir)
    elif upload_type == 'classes':
        process_department_class_file(temp_dir)

    os.remove(file_path)
    shutil.rmtree(temp_dir)


def process_class_course_files(extracted_dir):
    class_course_path = os.path.join(extracted_dir, 'class course')
    if os.path.isdir(class_course_path):
        for department_name in os.listdir(class_course_path):
            department_path = os.path.join(class_course_path, department_name)
            if os.path.isdir(department_path):
                for class_file in os.listdir(department_path):
                    class_name, ext = os.path.splitext(class_file)
                    if ext == '.csv':
                        class_path = os.path.join(department_path, class_file)
                        try:
                            class_obj = Class.objects.get(
                                name=class_name, department__slug=department_name)
                            process_class_course_csv(class_path, class_obj)
                        except Class.DoesNotExist:
                            print(
                                f"Class {class_name} in department {department_name} does not exist in the database.")


def process_department_class_file(extracted_dir):
    department_class_path = os.path.join(extracted_dir, 'classes')
    if os.path.isdir(department_class_path):
        for department_name in os.listdir(department_class_path):
            department_path = os.path.join(
                department_class_path, department_name)
            if os.path.isdir(department_path):
                class_file_path = os.path.join(department_path, 'classes.csv')
                if os.path.isfile(class_file_path):
                    try:
                        department = Department.objects.get(
                            slug=department_name)
                        process_department_class_csv(
                            class_file_path, department)
                    except Department.DoesNotExist:
                        print(
                            f"Department {department_name} does not exist in the database.")


def process_class_course_csv(file_path, class_obj):
    file = pd.read_csv(file_path).to_dict()
    for key in file['COURSE CODE']:
        code = file['COURSE CODE'][key]
        name = file['COURSE TITLE'][key]
        exam_type = file['EXAM TYPE'][key]
        course, created = Course.objects.get_or_create(
            name=name, code=code, exam_type=exam_type)
        class_obj.courses.add(course)


def process_department_class_csv(class_file_path, department):
    file = pd.read_csv(class_file_path).to_dict()
    for key in file['Name']:
        Class.objects.update_or_create(
            name=file['Name'][key],
            department=department,
            size=file['Size'][key]
        )

##########################################################################################
################# Seat Allocation ########################################################
##########################################################################################


def allocate_students_to_seats(students, rows, cols, max_attempts=10000):
    """
    Optimized seat allocation with multi-pass approach and flexible constraints.
    Uses pattern-based seating and fallback mechanisms to maximize placement.
    """
    if not students:  # Check if students list is empty
        return {}, students, 0  # Return all students as unplaced with 0% placement

    # Initialize seat grid and student tracking
    seats = [[None for _ in range(cols)] for _ in range(rows)]
    student_positions = {student['name']: None for student in students}
    
    # Group students by course for better placement strategies
    course_groups = {}
    for student in students:
        course = student['course']
        if course not in course_groups:
            course_groups[course] = []
        course_groups[course].append(student)
    
    def is_valid_position(student_name, row, col):
        """Check if position is valid - STRICT enforcement of adjacency constraints"""
        course = next(student['course'] for student in students if student['name'] == student_name)
        
        # Define adjacency directions (8-directional) - ALWAYS check all directions
        # This ensures NO students from same course can sit adjacent horizontally, vertically, or diagonally
        directions = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
        
        for dr, dc in directions:
            r, c = row + dr, col + dc
            if 0 <= r < rows and 0 <= c < cols and seats[r][c]:
                adjacent_student = next(
                    student for student in students if student['name'] == seats[r][c])
                if adjacent_student['course'] == course:
                    return False
        return True
    
    def try_pattern_placement(course_students, pattern='checkerboard'):
        """Try to place students using specific patterns"""
        placed = 0
        
        if pattern == 'checkerboard':
            # Try checkerboard pattern (every other seat)
            positions = [(r, c) for r in range(rows) for c in range(cols) 
                        if (r + c) % 2 == 0 and not seats[r][c]]
        elif pattern == 'diagonal':
            # Try diagonal pattern
            positions = [(r, c) for r in range(rows) for c in range(cols) 
                        if r % 2 == c % 2 and not seats[r][c]]
        else:
            # Sequential pattern
            positions = [(r, c) for r in range(rows) for c in range(cols) if not seats[r][c]]
        
        random.shuffle(positions)
        
        for student in course_students:
            if student_positions[student['name']] is not None:
                continue  # Already placed
                
            for row, col in positions:
                if not seats[row][col] and is_valid_position(student['name'], row, col):
                    seats[row][col] = student['name']
                    student_positions[student['name']] = (row, col)
                    positions.remove((row, col))
                    placed += 1
                    break
        
        return placed
    
    def try_random_placement(remaining_students, attempts_per_student=100):
        """Try random placement with STRICT adjacency constraints"""
        placed = 0
        
        for student in remaining_students:
            if student_positions[student['name']] is not None:
                continue  # Already placed
                
            for _ in range(attempts_per_student):
                row, col = random.randint(0, rows-1), random.randint(0, cols-1)
                if not seats[row][col] and is_valid_position(student['name'], row, col):
                    seats[row][col] = student['name']
                    student_positions[student['name']] = (row, col)
                    placed += 1
                    break
        
        return placed
    
    # Multi-pass allocation strategy with STRICT adjacency enforcement
    total_placed = 0
    
    # Pass 1: Pattern-based placement for each course
    patterns = ['checkerboard', 'diagonal', 'sequential']
    for course, course_students in course_groups.items():
        random.shuffle(course_students)  # Randomize within course
        
        for pattern in patterns:
            remaining = [s for s in course_students if student_positions[s['name']] is None]
            if not remaining:
                break
            placed = try_pattern_placement(remaining, pattern)
            total_placed += placed
            if placed > 0:
                break  # If pattern worked, move to next course
    
    # Pass 2: Random placement with strict constraints - increased attempts
    remaining_students = [s for s in students if student_positions[s['name']] is None]
    if remaining_students:
        placed = try_random_placement(remaining_students, 300)
        total_placed += placed
    
    # Pass 3: Final attempt with more intensive random placement
    remaining_students = [s for s in students if student_positions[s['name']] is None]
    if remaining_students:
        placed = try_random_placement(remaining_students, 500)
        total_placed += placed
    
    # NOTE: Removed relaxed and force placement passes to maintain strict adjacency constraints
    # Students that cannot be placed while maintaining constraints will remain unplaced
    
    # Convert positions to sequential seat numbers
    def index_to_seat(row, col):
        return row * cols + col + 1
    
    seat_positions = {}
    unplaced_students = []
    
    for student, position in student_positions.items():
        if position is None:
            unplaced_students.append(student)
        else:
            row, col = position
            if row is not None and col is not None:
                seat_positions[student] = index_to_seat(row, col)
            else:
                unplaced_students.append(student)
    
    # Calculate placement statistics
    placed_count = len(seat_positions)
    total_students = len(students)
    percentage_placed = (placed_count / total_students) * 100 if total_students > 0 else 0
    
    # Print debug information
    print(f"Total students: {total_students}")
    print(f"Placed students count: {placed_count}")
    print(f"Unplaced students: {len(unplaced_students)}")
    print(f"Percentage placed: {percentage_placed:.2f}%")
    
    # Lower the threshold to 60% and always return results
    if percentage_placed >= 60:
        return seat_positions, unplaced_students, percentage_placed
    else:
        # Even if below threshold, return partial results instead of empty
        return seat_positions, unplaced_students, percentage_placed


def print_seating_arrangement(students, rows, cols, date, period, hall_id):
    from .models import Student  # Import here to avoid circular imports
    
    result = allocate_students_to_seats(students, rows, cols)
    if result is None:
        print("Error: allocate_students_to_seats returned None.")
        return

    seat_positions, unplaced_students, percentage_placed = result

    print(f"Percentage of students placed: {percentage_placed:.2f}%")

    if seat_positions:
        # Group students by course
        courses = sorted(set(student['course'] for student in students))
        course_groups = {course: [] for course in courses}
        for student_name, seat in seat_positions.items():
            student_data = next(s for s in students if s['name'] == student_name)
            course = student_data['course']
            cls_id = student_data['cls_id']
            student_id = student_data.get('student_id')
            course_groups[course].append((student_name, seat, cls_id, student_id))

        # Print sorted by course and create SeatArrangement objects
        print("\nSeating Arrangement:")
        for course in courses:
            print(f"\n{course}:")
            arrangements = []
            for student_name, seat, cls_id, student_id in sorted(course_groups[course], key=lambda x: x[0]):
                # Get the actual Student instance if student_id exists
                student_instance = None
                if student_id:
                    try:
                        student_instance = Student.objects.get(id=student_id)
                    except Student.DoesNotExist:
                        student_instance = None
                
                arrangements.append(
                    SeatArrangement(
                        date=date,
                        period=period,
                        student=student_instance,  # Use actual Student instance
                        seat_number=seat,
                        hall=Hall.objects.get(id=hall_id),
                        course=Course.objects.filter(code=course).first(),
                        cls=Class.objects.get(id=cls_id)
                    )
                )
                print(f"{student_name}: {seat}")
            SeatArrangement.objects.bulk_create(arrangements)

    # Group and sort unplaced students by course
    unplaced_by_course = {}
    for student_name in unplaced_students:
        student_data = next(s for s in students if s['name'] == student_name)
        course = student_data['course']
        cls_id = student_data['cls_id']
        student_id = student_data.get('student_id')
        if course not in unplaced_by_course:
            unplaced_by_course[course] = []
        unplaced_by_course[course].append((student_name, cls_id, student_id))

    # Print unplaced students sorted by course and create SeatArrangement objects
    if unplaced_students:
        print("\nUnplaced Students:")
        for course in sorted(unplaced_by_course.keys()):
            print(f"\n{course}:")
            arrangements = []
            for student_name, cls_id, student_id in sorted(unplaced_by_course[course]):
                # Get the actual Student instance if student_id exists
                student_instance = None
                if student_id:
                    try:
                        student_instance = Student.objects.get(id=student_id)
                    except Student.DoesNotExist:
                        student_instance = None
                
                arrangements.append(
                    SeatArrangement(
                        date=date,
                        period=period,
                        student=student_instance,  # Use actual Student instance
                        hall=Hall.objects.get(id=hall_id),
                        course=Course.objects.filter(code=course).first(),
                        cls=Class.objects.get(id=cls_id)
                    )
                )
                print(student_name)
            SeatArrangement.objects.bulk_create(arrangements)


def generate_seat_allocation(rows: int, cols: int, students):
    random.seed(0)
    # Ensure the total number of students does not exceed rows * cols
    if len(students) > rows * cols:
        print(
            f"Error: Too many students for the given hall capacity of {rows * cols} seats.")
    else:
        # Print the seating arrangement
        print_seating_arrangement(students, rows, cols)


def is_valid_position(seat_number, course_code, seat_map, rows, cols):
    """
    Check if a seat position is valid for manual assignment based on adjacency constraints.
    
    Args:
        seat_number (int): The seat number to check (1-based)
        course_code (str): The course code of the student to be placed
        seat_map (dict): Dictionary mapping seat numbers to course codes
        rows (int): Number of rows in the hall
        cols (int): Number of columns in the hall
    
    Returns:
        bool: True if the position is valid, False otherwise
    """
    # Convert seat number to row, col (0-based)
    seat_index = seat_number - 1
    row = seat_index // cols
    col = seat_index % cols
    
    # Define adjacency directions (8-directional)
    directions = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
    
    for dr, dc in directions:
        adj_row, adj_col = row + dr, col + dc
        
        # Check if adjacent position is within bounds
        if 0 <= adj_row < rows and 0 <= adj_col < cols:
            # Convert back to seat number
            adj_seat_number = adj_row * cols + adj_col + 1
            
            # Check if there's a student in the adjacent seat with the same course
            if adj_seat_number in seat_map and seat_map[adj_seat_number] == course_code:
                return False
    
    return True


def get_student_number(dep_slug, cls, num):
    student_number = ""
    if cls.name.startswith("N"):
        student_number += "N/"
    elif cls.name.startswith("P"):
        student_number += "PN/"
    else:
        student_number += "H/"
    student_number += f"{dep_slug}/{num:04}"
    return student_number
