"""
Ornek katalog verisi ekler. Gercek ogrenci veya okul verisi icermez.
Uygulamayi bir kez calistirdiktan sonra (veya dogrudan) su komut yeterli:

    python seed_data.py

Veritabaninda zaten kitap varsa tekrar ekleme yapmaz.
"""
from datetime import datetime, timedelta

from app import (
    app,
    db,
    init_db,
    Category,
    Book,
    Student,
    Borrow,
    Review,
)


SAMPLE_BOOKS = [
    {
        "title": "Pride and Prejudice",
        "author": "Jane Austen",
        "description": "A classic novel about manners, marriage, and misunderstanding in 19th-century England.",
        "category": "Novel",
        "isbn": "9780141439518",
        "page_count": 432,
        "publish_year": 1813,
        "quantity": 3,
        "available": 2,
        "floor": 1,
        "shelf": "A3",
    },
    {
        "title": "Frankenstein",
        "author": "Mary Shelley",
        "description": "A science fiction novel about a scientist who creates life and faces the consequences.",
        "category": "Science Fiction",
        "isbn": "9780141439471",
        "page_count": 280,
        "publish_year": 1818,
        "quantity": 2,
        "available": 2,
        "floor": 2,
        "shelf": "B1",
    },
    {
        "title": "The Time Machine",
        "author": "H. G. Wells",
        "description": "A traveler moves far into the future and finds a divided human society.",
        "category": "Science Fiction",
        "isbn": "9780141439976",
        "page_count": 118,
        "publish_year": 1895,
        "quantity": 2,
        "available": 1,
        "floor": 2,
        "shelf": "B2",
    },
    {
        "title": "The Adventures of Sherlock Holmes",
        "author": "Arthur Conan Doyle",
        "description": "A collection of detective stories featuring Sherlock Holmes and Dr. Watson.",
        "category": "Adventure",
        "isbn": "9780140437713",
        "page_count": 334,
        "publish_year": 1892,
        "quantity": 4,
        "available": 4,
        "floor": 1,
        "shelf": "C1",
    },
    {
        "title": "Meditations",
        "author": "Marcus Aurelius",
        "description": "Personal notes on Stoic philosophy, written by a Roman emperor.",
        "category": "Philosophy",
        "isbn": "9780140449334",
        "page_count": 254,
        "publish_year": 180,
        "quantity": 2,
        "available": 2,
        "floor": 3,
        "shelf": "D2",
    },
    {
        "title": "On the Origin of Species",
        "author": "Charles Darwin",
        "description": "The foundational work that introduced the theory of evolution by natural selection.",
        "category": "Science",
        "isbn": "9780140439120",
        "page_count": 576,
        "publish_year": 1859,
        "quantity": 2,
        "available": 2,
        "floor": 3,
        "shelf": "E1",
    },
    {
        "title": "Alice's Adventures in Wonderland",
        "author": "Lewis Carroll",
        "description": "A girl follows a white rabbit into a world of unusual characters and wordplay.",
        "category": "Children",
        "isbn": "9780141439761",
        "page_count": 192,
        "publish_year": 1865,
        "quantity": 3,
        "available": 3,
        "floor": 1,
        "shelf": "F4",
    },
    {
        "title": "The Histories",
        "author": "Herodotus",
        "description": "An early historical account of the Greco-Persian Wars and the peoples around them.",
        "category": "History",
        "isbn": "9780140449082",
        "page_count": 716,
        "publish_year": 430,
        "quantity": 1,
        "available": 1,
        "floor": 2,
        "shelf": "G2",
    },
]

SAMPLE_STUDENTS = [
    {
        "student_number": "STU1001",
        "name": "Ada Yılmaz",
        "email": "ada.yilmaz@example.com",
        "phone": "05550001001",
        "department": "Computer Engineering",
    },
    {
        "student_number": "STU1002",
        "name": "Mert Kaya",
        "email": "mert.kaya@example.com",
        "phone": "05550001002",
        "department": "Industrial Engineering",
    },
]


def seed():
    init_db()

    if Book.query.first():
        print("Sample data already exists. Nothing was added.")
        return

    categories = {c.name: c for c in Category.query.all()}

    books = {}
    for item in SAMPLE_BOOKS:
        cat = categories.get(item["category"])
        book = Book(
            title=item["title"],
            author=item["author"],
            description=item["description"],
            category_id=cat.id if cat else None,
            isbn=item["isbn"],
            page_count=item["page_count"],
            publish_year=item["publish_year"],
            quantity=item["quantity"],
            available=item["available"],
            floor=item["floor"],
            shelf=item["shelf"],
        )
        db.session.add(book)
        books[item["title"]] = book

    students = {}
    for item in SAMPLE_STUDENTS:
        student = Student(**item)
        db.session.add(student)
        students[item["student_number"]] = student

    db.session.flush()

    now = datetime.utcnow()

    active = Borrow(
        book_id=books["The Time Machine"].id,
        student_id=students["STU1002"].id,
        borrow_date=now - timedelta(days=5),
        due_date=now + timedelta(days=9),
        status="active",
        notes="Sample active borrow",
    )
    returned = Borrow(
        book_id=books["Pride and Prejudice"].id,
        student_id=students["STU1001"].id,
        borrow_date=now - timedelta(days=20),
        due_date=now - timedelta(days=6),
        return_date=now - timedelta(days=8),
        status="returned",
        notes="Sample returned borrow",
    )
    db.session.add_all([active, returned])

    review = Review(
        book_id=books["Pride and Prejudice"].id,
        student_id=students["STU1001"].id,
        rating=5,
        comment="A sample review. Sharp characters and a story that still holds up.",
    )
    db.session.add(review)

    db.session.commit()
    print("Sample catalog, students, borrows, and one review were added.")
    print("These records are fictional examples for local testing.")


if __name__ == "__main__":
    with app.app_context():
        seed()
