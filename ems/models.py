# Create your models here.
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models


class Department(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=10)

    def __str__(self) -> str:
        return str(self.name)


class SystemSettings(models.Model):
    session = models.CharField(
        max_length=200, default="2024/2025", unique=True)
    semester = models.CharField(max_length=100, default="1st Semester")
    has_timetable = models.BooleanField(default=False)

    def __str__(self):
        return str(f"{self.session} ' - ' {self.semester}")


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=30, blank=True)
    last_name = models.CharField(max_length=30, blank=True)
    department = models.ForeignKey(
        Department, on_delete=models.CASCADE, null=True, blank=True
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    objects = UserManager()

    def __str__(self):
        return self.email


class Course(models.Model):
    COURSE_TYPE = (("PBE", "PBE"), ("CBE", "CBE"))
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50)
    exam_type = models.CharField(
        max_length=50, default="PBE", choices=COURSE_TYPE)

    def __str__(self) -> str:
        return f"{self.name} - {self.code}"


class Class(models.Model):
    name = models.CharField(max_length=25, null=True, blank=True)
    courses = models.ManyToManyField(Course, related_name="courses")
    department = models.ForeignKey(
        Department, related_name="class_dep", on_delete=models.CASCADE
    )
    size = models.IntegerField()

    def __str__(self) -> str:
        return f"{self.name} - {self.department.name}"


class Hall(models.Model):
    name = models.CharField(max_length=255)
    capacity = models.IntegerField()
    max_students = models.IntegerField(default=0)
    min_courses = models.IntegerField(default=0)
    rows = models.IntegerField()
    columns = models.IntegerField()

    def __str__(self) -> str:
        return str(self.name)


PERIOD = (('AM', 'AM'), ('PM', 'PM'))


class TimeTable(models.Model):

    course = models.ForeignKey(
        Course, related_name="timetable_course", on_delete=models.CASCADE)
    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE,
                                  related_name="timetable_class")
    period = models.CharField(max_length=50, choices=PERIOD)
    date = models.DateField()

    def __str__(self) -> str:
        return f"{self.class_obj.department.name} | {self.course.code} | {self.date} | {self.period}"


class DistributionItem(models.Model):
    schedule = models.ForeignKey(TimeTable, on_delete=models.CASCADE)
    no_of_students = models.IntegerField()


class Distribution(models.Model):
    hall = models.ForeignKey(Hall, on_delete=models.CASCADE)
    items = models.ManyToManyField(DistributionItem)
    date = models.CharField(max_length=15, null=True)
    period = models.CharField(max_length=2, null=True)


class Student(models.Model):
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    matric_no = models.CharField(max_length=15, unique=True)
    email = models.EmailField(unique=True)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    level = models.ForeignKey(Class, on_delete=models.CASCADE)
    phone = models.CharField(max_length=15, blank=True)

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name} - {self.matric_no}"


class SeatArrangement(models.Model):
    period = models.CharField(max_length=50, choices=PERIOD)
    date = models.DateField()
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, null=True, blank=True)
    seat_number = models.IntegerField(null=True, blank=True)
    hall = models.ForeignKey(Hall, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    cls = models.ForeignKey(Class, on_delete=models.CASCADE)

    def __str__(self) -> str:
        return f"{self.student.matric_no} - {self.seat_number or 'None'} - Course {self.course.code} - Date {self.date} - Period {self.period}"
