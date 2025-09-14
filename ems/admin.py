from django.contrib import admin
from .models import User, Department, Course, Class, TimeTable, Hall, Distribution, DistributionItem, SeatArrangement, Student, SystemSettings


# Register your models here.


admin.site.register(User)
admin.site.register(Department)
admin.site.register(Course)
admin.site.register(Class)
admin.site.register(TimeTable)
admin.site.register(Hall)
admin.site.register(Distribution)
admin.site.register(DistributionItem)
admin.site.register(SeatArrangement)
admin.site.register(Student)
admin.site.register(SystemSettings)
