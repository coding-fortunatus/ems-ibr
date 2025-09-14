from django.urls import path

from . import csv_gen, views

urlpatterns = [
    path("", view=views.index, name="home"),
    path("login/", view=views.login_view, name="login"),
    path("logout/", view=views.logout_view, name="logout"),
    path("dashboard/", view=views.dashboard, name="dashboard"),
    path("departments/", view=views.departments, name="department"),
    path('back/', views.back_view, name='back'),
    path(
        "upload-departments/", view=views.upload_departments, name="upload-departments"
    ),
    path("halls/", view=views.halls, name="halls"),
    path("timetable/", view=views.timetable, name="timetable"),
    path("distribution/", view=views.distribution, name="distribution"),
    path("allocation/", view=views.allocation, name="allocation"),
    path("manage-users/", view=views.manage_users, name="manage_users"),
    path("departments/<str:slug>/",
         view=views.get_department, name="get_department"),
    path(
        "upload-classes/<str:dept_slug>/",
        view=views.upload_classes,
        name="upload_classes",
    ),
    path(
        "departments/<str:slug>/<int:id>/",
        view=views.get_class_course,
        name="get_class_course",
    ),
    path("courses/", view=views.get_courses_view, name="courses"),

    path("students/", view=views.get_students, name="students"),
    path("add-user/", view=views.add_user, name="add-user"),
    path(
        "upload-class-courses/<int:id>/",
        view=views.upload_class_courses,
        name="upload_class_courses",
    ),
    path(
        "upload-class-students/<int:id>/",
        view=views.upload_class_students,
        name="upload_class_students",
    ),
    path("upload-halls/", view=views.upload_halls, name="upload_halls"),
    path("upload-courses/", view=views.upload_courses, name="upload_courses"),
    path("generate-timetable", view=views.generate_timetable,
         name="generate_timetable"),
    path("distribute-halls", view=views.generate_distribution,
         name="generate_distribution"),
    path("distribution-statistics/", view=views.distribution_statistics,
         name="distribution_statistics"),
    path("generate-allocation", view=views.generate_allocation,
         name="generate_allocation"),
    path('export-timetable', csv_gen.export_department_timetable,
         name='export_timetable'),
    path('export-distribution/',
         csv_gen.export_distribution, name="export_distribution"),
    path('export-arrangement/',
         csv_gen.export_arrangements, name="export_arrangement"),
    path('generate-attendance-sheets/', view=views.generate_attendance_sheets,
         name="generate_attendance_sheets"),
    path('generate_broadsheet/', view=views.generate_broadsheet,
         name="generate_broadsheet"),
    path('hall-allocation/', view=views.hall_allocation, name="hall_allocation"),
    path('manual-seat-assignment/', view=views.manual_seat_assignment,
         name="manual_seat_assignment"),
    path('bulk-upload', view=views.bulk_upload, name='bulk-upload'),
    path('reset', view=views.reset_system, name="reset-system"),
    path('settings', view=views.setting, name="settings"),
    path("settings/update/", views.update_settings, name="update-settings"),

]
