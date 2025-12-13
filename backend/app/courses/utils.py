from purchases.models import Purchase


def user_has_course_access(user, course) -> bool:
    if course.is_free:
        return True
    if not user or not user.is_authenticated:
        return False
    return Purchase.objects.filter(user=user, course=course, status="paid").exists()

