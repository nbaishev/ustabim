from django.core.management.base import BaseCommand
from django.db import transaction
from courses.models import Course, Module, Lesson


COURSES = [
    {
        "id": "revit-basics",
        "title": "Основы Autodesk Revit",
        "description": "Полное введение в BIM-проектирование для начинающих",
        "full_description": "Этот курс предназначен для тех, кто только начинает изучать Autodesk Revit. Вы научитесь создавать архитектурные модели, работать с семействами, настраивать виды и листы, а также освоите основные инструменты моделирования.",
        "is_free": True,
        "level": "Начинающий",
        "price": None,
        "preview_image": "/placeholder.svg",
        "is_featured": True,
        "modules": [
            {
                "title": "Введение в Revit",
                "lessons": [
                    {"title": "Интерфейс программы", "duration": "15:00", "video_id": "dQw4w9WgXcQ"},
                    {"title": "Настройка проекта", "duration": "20:00", "video_id": "dQw4w9WgXcQ"},
                    {"title": "Навигация по модели", "duration": "18:00", "video_id": "dQw4w9WgXcQ"},
                ],
            },
            {
                "title": "Базовое моделирование",
                "lessons": [
                    {"title": "Стены и перегородки", "duration": "25:00", "video_id": "dQw4w9WgXcQ"},
                    {"title": "Двери и окна", "duration": "22:00", "video_id": "dQw4w9WgXcQ"},
                    {"title": "Перекрытия", "duration": "20:00", "video_id": "dQw4w9WgXcQ"},
                    {"title": "Крыши", "duration": "30:00", "video_id": "dQw4w9WgXcQ"},
                ],
            },
            {
                "title": "Оформление документации",
                "lessons": [
                    {"title": "Создание видов", "duration": "20:00", "video_id": "dQw4w9WgXcQ"},
                    {"title": "Размеры и аннотации", "duration": "25:00", "video_id": "dQw4w9WgXcQ"},
                    {"title": "Листы и штампы", "duration": "22:00", "video_id": "dQw4w9WgXcQ"},
                ],
            },
        ],
    },
    {
        "id": "revit-architecture",
        "title": "Архитектурное проектирование в Revit",
        "description": "Продвинутые техники архитектурного моделирования",
        "full_description": "Углублённый курс по архитектурному проектированию. Изучите сложные формы, адаптивные компоненты, работу с фасадами и создание детальной документации для строительства.",
        "is_free": False,
        "level": "Средний",
        "price": 4990,
        "preview_image": "/placeholder.svg",
        "is_featured": True,
        "modules": [
            {
                "title": "Сложные формы",
                "lessons": [
                    {"title": "Концептуальное моделирование", "duration": "30:00", "video_id": "dQw4w9WgXcQ"},
                    {"title": "Формообразующие", "duration": "35:00", "video_id": "dQw4w9WgXcQ"},
                    {"title": "Адаптивные компоненты", "duration": "40:00", "video_id": "dQw4w9WgXcQ"},
                ],
            },
            {
                "title": "Фасадные системы",
                "lessons": [
                    {"title": "Витражи и панели", "duration": "35:00", "video_id": "dQw4w9WgXcQ"},
                    {"title": "Навесные фасады", "duration": "40:00", "video_id": "dQw4w9WgXcQ"},
                ],
            },
        ],
    },
    {
        "id": "revit-mep",
        "title": "Инженерные системы в Revit MEP",
        "description": "Проектирование ОВиК, ВК и электрики",
        "full_description": "Полный курс по проектированию инженерных систем в Revit MEP. Охватывает вентиляцию, кондиционирование, водоснабжение, канализацию и электрические системы.",
        "is_free": False,
        "level": "Средний",
        "price": 5990,
        "preview_image": "/placeholder.svg",
        "is_featured": True,
        "modules": [
            {
                "title": "ОВиК",
                "lessons": [
                    {"title": "Воздуховоды", "duration": "30:00", "video_id": "dQw4w9WgXcQ"},
                    {"title": "Оборудование", "duration": "25:00", "video_id": "dQw4w9WgXcQ"},
                ],
            },
        ],
    },
    {
        "id": "revit-structure",
        "title": "Конструкции в Revit Structure",
        "description": "Проектирование несущих конструкций",
        "full_description": "Изучите проектирование железобетонных и металлических конструкций, армирование, создание рабочей документации для строительства.",
        "is_free": False,
        "level": "Средний",
        "price": 4490,
        "preview_image": "/placeholder.svg",
        "is_featured": False,
        "modules": [
            {
                "title": "Основы",
                "lessons": [
                    {"title": "Введение в Revit Structure", "duration": "20:00", "video_id": "dQw4w9WgXcQ"},
                ],
            },
        ],
    },
    {
        "id": "revit-families",
        "title": "Создание семейств в Revit",
        "description": "Мастер-класс по созданию параметрических семейств",
        "full_description": "Научитесь создавать собственные параметрические семейства для любых задач. От простых элементов до сложных адаптивных компонентов.",
        "is_free": False,
        "level": "Продвинутый",
        "price": 6990,
        "preview_image": "/placeholder.svg",
        "is_featured": False,
        "modules": [
            {
                "title": "Основы семейств",
                "lessons": [
                    {"title": "Типы семейств", "duration": "25:00", "video_id": "dQw4w9WgXcQ"},
                ],
            },
        ],
    },
    {
        "id": "revit-dynamo",
        "title": "Dynamo для Revit",
        "description": "Визуальное программирование и автоматизация",
        "full_description": "Освойте Dynamo для автоматизации рутинных задач, генеративного дизайна и работы с данными в Revit проектах.",
        "is_free": False,
        "level": "Продвинутый",
        "price": 7490,
        "preview_image": "/placeholder.svg",
        "is_featured": False,
        "modules": [
            {
                "title": "Введение в Dynamo",
                "lessons": [
                    {"title": "Интерфейс Dynamo", "duration": "20:00", "video_id": "dQw4w9WgXcQ"},
                ],
            },
        ],
    },
]


class Command(BaseCommand):
    help = "Seed initial courses, modules, and lessons"

    @transaction.atomic
    def handle(self, *args, **options):
        created_count = 0
        for course_data in COURSES:
            course, created = Course.objects.get_or_create(
                id=course_data["id"],
                defaults={
                    "title": course_data["title"],
                    "description": course_data["description"],
                    "full_description": course_data["full_description"],
                    "is_free": course_data["is_free"],
                    "level": course_data["level"],
                    "price": course_data["price"],
                    "preview_image": course_data["preview_image"],
                    "is_featured": course_data.get("is_featured", False),
                },
            )
            if created:
                created_count += 1

            course.modules.all().delete()
            for module_index, module_data in enumerate(course_data["modules"], start=1):
                module = Module.objects.create(
                    course=course,
                    title=module_data["title"],
                    order=module_index,
                )
                for lesson_index, lesson_data in enumerate(module_data["lessons"], start=1):
                    Lesson.objects.create(
                        module=module,
                        title=lesson_data["title"],
                        duration=lesson_data.get("duration", ""),
                        order=lesson_index,
                        video_url=f"https://www.youtube.com/watch?v={lesson_data['video_id']}",
                    )
        self.stdout.write(self.style.SUCCESS(f"Seeded courses. New courses: {created_count}"))

