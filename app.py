"""
=============================================================================
KUTUPHANE YONETIM SISTEMI (Library Management System)
=============================================================================
Bu uygulama Flask web framework'u kullanilarak gelistirilmis bir 
kutuphane yonetim sistemidir.

Ozellikler:
- Kitap, ogrenci, kategori yonetimi
- Odunc verme ve iade takibi
- AI tabanli kitap onerisi
- Yorum ve puanlama sistemi
- CSV export ozelligi
- QR kod ile erisim

Teknolojiler:
- Backend: Python, Flask
- Veritabani: SQLite (Flask-SQLAlchemy ORM)
- Frontend: HTML, CSS, JavaScript (Jinja2 template engine)
- AI: Anthropic Claude API

Yazar: Necdet Emre Bayraktar
=============================================================================
"""

# =============================================================================
# KUTUPHANELER (IMPORTS)
# =============================================================================

# Flask: Python web framework - web uygulamasi olusturmak icin kullanilir
# render_template: HTML sablonlarini render etmek icin
# request: HTTP isteklerinden veri almak icin (form verileri, URL parametreleri)
# redirect: Kullaniciyi baska bir sayfaya yonlendirmek icin
# url_for: URL olusturmak icin (route isimlerinden URL uretir)
# flash: Kullaniciya tek seferlik mesaj gostermek icin (basari, hata mesajlari)
# session: Kullanici oturumu yonetimi icin (giris bilgilerini saklar)
# jsonify: Python sozlugunu JSON formatina cevirmek icin (API yaniti)
# Response: HTTP yaniti olusturmak icin (CSV indirme gibi)
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, Response

# SQLAlchemy: Veritabani islemleri icin ORM (Object Relational Mapping)
# Python nesnelerini veritabani tablolarina esler
from flask_sqlalchemy import SQLAlchemy

# Sifre guvenlik fonksiyonlari
# generate_password_hash: Sifreyi hashleyerek guvenli hale getirir
# check_password_hash: Girilen sifre ile hash'i karsilastirir
from werkzeug.security import generate_password_hash, check_password_hash

# secure_filename: Yuklenen dosya adini guvenli hale getirir
from werkzeug.utils import secure_filename

# Tarih ve zaman islemleri icin
from datetime import datetime, timedelta

# wraps: Decorator fonksiyonlarinda orijinal fonksiyon bilgilerini korur
from functools import wraps

# os: Isletim sistemi islemleri (dosya yolu, klasor olusturma)
import os

# socket: Ag islemleri (yerel IP adresini almak icin)
import socket

# qrcode: QR kod olusturmak icin
import qrcode

# BytesIO, StringIO: Bellekte dosya olusturmak icin
from io import BytesIO, StringIO

# base64: Binary veriyi metin formatina cevirmek icin
import base64

# csv: CSV dosyasi olusturmak icin (veri export)
import csv

# .env dosyasindan ortam degiskenlerini yukle (yoksa sessizce gec)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# =============================================================================
# UYGULAMA YAPILANDIRMASI (APPLICATION CONFIGURATION)
# =============================================================================

# Flask uygulamasini olustur
app = Flask(__name__)

# Gizli anahtar - Session verilerini sifrelemek icin kullanilir
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change-me-in-development')

# Veritabani baglanti adresi (SQLite)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///library.db'

# SQLAlchemy degisiklik takibini kapat (performans icin)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Dosya yukleme klasoru - Kitap kapak resimleri burada saklanir
app.config['UPLOAD_FOLDER'] = os.path.join(app.static_folder, 'uploads')

# Maksimum dosya boyutu: 16 MB
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# SQLAlchemy veritabani nesnesini olustur
db = SQLAlchemy(app)

# Izin verilen dosya uzantilari (guvenlik icin)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def allowed_file(filename):
    """
    Yuklenen dosyanin izin verilen uzantiya sahip olup olmadigini kontrol eder.
    
    Parametreler:
        filename (str): Kontrol edilecek dosya adi
    
    Dondurur:
        bool: Dosya uzantisi izinli ise True, degilse False
    """
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# =============================================================================
# CONTEXT PROCESSOR - TUM TEMPLATE'LERDE KULLANILABILIR FONKSIYONLAR
# =============================================================================

@app.context_processor
def utility_processor():
    """
    Tum template'lerde kullanilabilecek fonksiyonlari tanimlar.
    Bu fonksiyonlar her template renderinda otomatik olarak eklenir.
    """
    def get_categories():
        """Tum kategorileri dondurur - Sidebar menusunde kullanilir."""
        return Category.query.order_by(Category.name).all()
    
    def now():
        """Su anki zamani dondurur - Gecikme hesaplamalarinda kullanilir."""
        return datetime.utcnow()
    
    return dict(get_categories=get_categories, now=now)


# =============================================================================
# VERITABANI MODELLERI (DATABASE MODELS)
# =============================================================================

class Admin(db.Model):
    """
    Admin (Yonetici) Modeli
    Sistem yoneticilerinin bilgilerini saklar.
    """
    # Birincil anahtar - Her kayit icin benzersiz numara
    id = db.Column(db.Integer, primary_key=True)
    
    # Kullanici adi - Benzersiz ve zorunlu
    username = db.Column(db.String(80), unique=True, nullable=False)
    
    # Hashlenmiş sifre - Guvenlik icin hash saklanir
    password_hash = db.Column(db.String(200), nullable=False)
    
    # Olusturma tarihi
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        """Sifreyi hashleyerek kaydeder."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Girilen sifrenin dogru olup olmadigini kontrol eder."""
        return check_password_hash(self.password_hash, password)


class Category(db.Model):
    """
    Kategori Modeli
    Kitap kategorilerini saklar (Roman, Bilim, Tarih vb.)
    """
    id = db.Column(db.Integer, primary_key=True)
    
    # Kategori adi - Benzersiz ve zorunlu
    name = db.Column(db.String(100), unique=True, nullable=False)
    
    # Bu kategorideki kitaplar (One-to-Many iliski)
    books = db.relationship('Book', backref='category', lazy=True)


class Book(db.Model):
    """
    Kitap Modeli
    Kutuphanedeki kitaplarin tum bilgilerini saklar.
    """
    id = db.Column(db.Integer, primary_key=True)
    
    # Temel bilgiler
    title = db.Column(db.String(200), nullable=False)  # Baslik
    author = db.Column(db.String(200), nullable=False)  # Yazar
    description = db.Column(db.Text)  # Aciklama
    image_path = db.Column(db.String(300))  # Kapak resmi dosya adi
    
    # Kategori iliskisi (Foreign Key)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))
    
    # Detay bilgileri
    isbn = db.Column(db.String(20))  # ISBN numarasi
    page_count = db.Column(db.Integer)  # Sayfa sayisi
    publish_year = db.Column(db.Integer)  # Basim yili
    
    # Stok bilgileri
    quantity = db.Column(db.Integer, default=1)  # Toplam adet
    available = db.Column(db.Integer, default=1)  # Mevcut adet
    
    # Konum bilgileri
    floor = db.Column(db.Integer, default=1)  # Kat
    shelf = db.Column(db.String(20), default='A')  # Raf
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Yorumlar iliskisi (kitap silinince yorumlar da silinir)
    reviews = db.relationship('Review', backref='book', lazy=True, cascade='all, delete-orphan')

    def average_rating(self):
        """Kitabin ortalama puanini hesaplar (1-5 arasi)."""
        if not self.reviews:
            return 0
        return round(sum(r.rating for r in self.reviews) / len(self.reviews), 1)


class Student(db.Model):
    """
    Ogrenci Modeli
    Kutuphaneye kayitli ogrencilerin bilgilerini saklar.
    """
    id = db.Column(db.Integer, primary_key=True)
    
    # Ogrenci numarasi - Benzersiz ve zorunlu
    student_number = db.Column(db.String(20), unique=True, nullable=False)
    
    # Kisisel bilgiler
    name = db.Column(db.String(200), nullable=False)  # Ad soyad
    email = db.Column(db.String(200))  # E-posta
    phone = db.Column(db.String(20))  # Telefon
    department = db.Column(db.String(200))  # Bolum
    
    # Iliskiler
    borrows = db.relationship('Borrow', backref='student', lazy=True)
    reviews = db.relationship('Review', backref='student', lazy=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Borrow(db.Model):
    """
    Odunc (Borrow) Modeli
    Kitap odunc verme islemlerini takip eder.
    """
    id = db.Column(db.Integer, primary_key=True)
    
    # Hangi kitap, hangi ogrenci (Foreign Keys)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    
    # Tarihler
    borrow_date = db.Column(db.DateTime, default=datetime.utcnow)  # Odunc alma
    due_date = db.Column(db.DateTime, nullable=False)  # Son iade tarihi
    return_date = db.Column(db.DateTime)  # Gercek iade tarihi
    
    # Durum: active (aktif), overdue (gecikmis), returned (iade edilmis)
    status = db.Column(db.String(20), default='active')
    notes = db.Column(db.Text)  # Notlar
    
    # Kitap iliskisi
    book = db.relationship('Book', backref='borrows')
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Review(db.Model):
    """
    Yorum (Review) Modeli
    Kitaplara yapilan yorum ve puanlamalari saklar.
    """
    id = db.Column(db.Integer, primary_key=True)
    
    # Hangi kitap, hangi ogrenci (Foreign Keys)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    
    # Puan (1-5 yildiz) ve yorum
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# =============================================================================
# YARDIMCI FONKSIYONLAR (HELPER FUNCTIONS)
# =============================================================================

def login_required(f):
    """
    Giris gerektiren sayfalari korumak icin decorator.
    Kullanici giris yapmamissa login sayfasina yonlendirir.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            flash('You must login to access this page.', 'warning')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function


def update_overdue_status():
    """
    Geciken odunc islemlerinin durumunu gunceller.
    Tarihi gecmis aktif kayitlari 'overdue' olarak isaretler.
    """
    overdue_borrows = Borrow.query.filter(
        Borrow.status == 'active',
        Borrow.due_date < datetime.utcnow()
    ).all()
    
    for borrow in overdue_borrows:
        borrow.status = 'overdue'
    
    db.session.commit()


def get_local_ip():
    """Bilgisayarin yerel ag IP adresini alir."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"


def generate_qr_code(url):
    """Verilen URL icin QR kod olusturur ve Base64 formatinda dondurur."""
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return base64.b64encode(buffer.getvalue()).decode()


def has_borrowed_book(student_number, book_id):
    """Ogrencinin belirli bir kitabi odunc alip almadigini kontrol eder."""
    student = Student.query.filter_by(student_number=student_number).first()
    if not student:
        return False
    borrow = Borrow.query.filter_by(student_id=student.id, book_id=book_id).first()
    return borrow is not None


def has_already_reviewed(student_number, book_id):
    """Ogrencinin belirli bir kitaba daha once yorum yapip yapmadigini kontrol eder."""
    student = Student.query.filter_by(student_number=student_number).first()
    if not student:
        return False
    review = Review.query.filter_by(student_id=student.id, book_id=book_id).first()
    return review is not None


# =============================================================================
# KULLANICI SAYFALARI (PUBLIC PAGES)
# =============================================================================

@app.route('/')
def index():
    """
    Ana Sayfa
    Son eklenen kitaplari ve genel istatistikleri gosterir.
    """
    update_overdue_status()
    
    # Son 6 kitap
    books = Book.query.order_by(Book.created_at.desc()).limit(6).all()
    
    # Istatistikler
    total_books = Book.query.count()
    total_categories = Category.query.count()
    active_borrows = Borrow.query.filter_by(status='active').count()
    
    return render_template('index.html', 
                          books=books, 
                          total_books=total_books, 
                          total_categories=total_categories, 
                          active_borrows=active_borrows)


@app.route('/books')
def books():
    """
    Kitap Listesi Sayfasi
    Arama, filtreleme ve sayfalama ozellikleri ile kitaplari listeler.
    """
    # URL parametreleri
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    category_id = request.args.get('category', type=int)
    
    # Sorgu olustur
    query = Book.query
    
    # Arama filtresi
    if search:
        query = query.filter((Book.title.ilike(f'%{search}%')) | (Book.author.ilike(f'%{search}%')))
    
    # Kategori filtresi
    if category_id:
        query = query.filter_by(category_id=category_id)
    
    # Sayfalama
    books = query.order_by(Book.title).paginate(page=page, per_page=12)
    categories = Category.query.order_by(Category.name).all()
    
    return render_template('books.html', books=books, categories=categories, search=search, selected_category=category_id)


@app.route('/book/<int:id>')
def book_detail(id):
    """
    Kitap Detay Sayfasi
    Kitabin tum bilgilerini, yorumlarini ve benzer kitaplari gosterir.
    """
    book = Book.query.get_or_404(id)
    similar_books = Book.query.filter(Book.category_id == book.category_id, Book.id != book.id).limit(4).all()
    reviews = Review.query.filter_by(book_id=id).order_by(Review.created_at.desc()).all()
    return render_template('book_detail.html', book=book, similar_books=similar_books, reviews=reviews)


@app.route('/book/<int:id>/review', methods=['POST'])
def add_review(id):
    """
    Kitaba Yorum Ekleme
    Sadece kitabi odunc almis ogrenciler yorum yapabilir.
    """
    book = Book.query.get_or_404(id)
    
    # Form verilerini al
    student_number = request.form.get('student_number', '').strip()
    rating = request.form.get('rating', type=int)
    comment = request.form.get('comment', '').strip()
    
    # Validasyonlar
    if not student_number:
        flash('Please enter your student number.', 'danger')
        return redirect(url_for('book_detail', id=id))
    
    if not rating or rating < 1 or rating > 5:
        flash('Please select a valid rating (1-5 stars).', 'danger')
        return redirect(url_for('book_detail', id=id))
    
    # Ogrenci kontrolu
    student = Student.query.filter_by(student_number=student_number).first()
    if not student:
        flash('Student number not found. Only registered students can leave reviews.', 'danger')
        return redirect(url_for('book_detail', id=id))
    
    # Odunc alma kontrolu
    if not has_borrowed_book(student_number, id):
        flash('You can only review books that you have borrowed.', 'warning')
        return redirect(url_for('book_detail', id=id))
    
    # Tekrar yorum kontrolu
    if has_already_reviewed(student_number, id):
        flash('You have already reviewed this book.', 'warning')
        return redirect(url_for('book_detail', id=id))
    
    # Yorum kaydet
    review = Review(book_id=id, student_id=student.id, rating=rating, comment=comment)
    db.session.add(review)
    db.session.commit()
    
    flash('Your review has been submitted successfully!', 'success')
    return redirect(url_for('book_detail', id=id))


@app.route('/category/<int:id>')
def category_books(id):
    """Secilen kategorideki kitaplari listeler."""
    category = Category.query.get_or_404(id)
    page = request.args.get('page', 1, type=int)
    books = Book.query.filter_by(category_id=id).paginate(page=page, per_page=12)
    return render_template('category.html', category=category, books=books)


@app.route('/ai-assistant')
def ai_assistant():
    """AI Asistan Sayfasi - Yapay zeka tabanli kitap oneri chatbot'u."""
    return render_template('ai_assistant.html')


@app.route('/about')
def about():
    """Hakkinda Sayfasi - Sistem hakkinda bilgi."""
    return render_template('about.html')


# =============================================================================
# AI API ENDPOINT
# =============================================================================

@app.route('/api/ai-recommend', methods=['POST'])
def ai_recommend():
    """
    AI Kitap Oneri API'si
    Kullanicinin mesajina gore kutuphanedeki kitaplardan oneri yapar.
    """
    try:
        import anthropic
        
        # Kullanici mesajini al
        data = request.get_json()
        user_message = data.get('message', '')
        
        if not user_message:
            return jsonify({'error': 'Message cannot be empty'}), 400
        
        # Kutuphanedeki kitaplari listele
        books = Book.query.all()
        book_list = []
        
        for book in books:
            category_name = book.category.name if book.category else 'Uncategorized'
            availability = 'Available' if book.available > 0 else 'Not Available'
            location = f"Floor {book.floor}, Shelf {book.shelf}"
            avg_rating = book.average_rating()
            rating_str = f"Rating: {avg_rating}/5" if avg_rating > 0 else "No ratings yet"
            book_list.append(f"- {book.title} | Author: {book.author} | Category: {category_name} | Status: {availability} ({book.available} copies) | Location: {location} | {rating_str}")
        
        books_context = "\n".join(book_list) if book_list else "No books available in the library yet."
        
        # AI icin sistem promptu
        system_prompt = f"""You are a library assistant. You help users find and choose books.

Available books in our library:
{books_context}

Rules:
1. Only recommend books from the list above
2. Use friendly and helpful language
3. Include the book's location (floor and shelf) information
4. Mention if a book is not available
5. Keep responses concise and clear
6. Do not use emojis"""

        # AI API cagrisi
        client = anthropic.Anthropic()
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}]
        )
        
        return jsonify({'response': message.content[0].text})
        
    except ImportError:
        return jsonify({'error': 'API configuration missing. Please set ANTHROPIC_API_KEY.'}), 500
    except Exception as e:
        return jsonify({'error': f'An error occurred: {str(e)}'}), 500


# =============================================================================
# ADMIN - GIRIS/CIKIS ISLEMLERI
# =============================================================================

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """
    Admin Giris Sayfasi
    Kullanici adi ve sifre ile giris yapilir.
    """
    # Zaten giris yapilmissa dashboard'a yonlendir
    if 'admin_id' in session:
        return redirect(url_for('admin_dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Admin'i bul ve sifre kontrol et
        admin = Admin.query.filter_by(username=username).first()
        
        if admin and admin.check_password(password):
            # Basarili giris - Session'a kaydet
            session['admin_id'] = admin.id
            session['admin_username'] = admin.username
            flash('Login successful!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid username or password!', 'danger')
    
    return render_template('admin/login.html')


@app.route('/admin/logout')
def admin_logout():
    """Admin Cikis - Session'i temizler."""
    session.pop('admin_id', None)
    session.pop('admin_username', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))


# =============================================================================
# ADMIN - DASHBOARD VE ISTATISTIKLER
# =============================================================================

@app.route('/admin')
@login_required
def admin_dashboard():
    """
    Admin Dashboard
    Genel istatistikler, grafikler ve uyarilar gosterilir.
    """
    update_overdue_status()
    
    # Temel istatistikler
    total_books = Book.query.count()
    total_categories = Category.query.count()
    total_students = Student.query.count()
    total_reviews = Review.query.count()
    active_borrows = Borrow.query.filter_by(status='active').count()
    overdue_borrows = Borrow.query.filter_by(status='overdue').count()
    
    # Son eklenen kitaplar
    recent_books = Book.query.order_by(Book.created_at.desc()).limit(5).all()
    
    # Son odunc islemleri
    recent_borrows = Borrow.query.order_by(Borrow.created_at.desc()).limit(5).all()
    
    # Geciken kitaplar listesi
    overdue_list = Borrow.query.filter_by(status='overdue').all()
    
    # ==================== GELISMIS ISTATISTIKLER ====================
    
    # En cok odunc alinan 5 kitap
    # SQL: SELECT book_id, COUNT(*) as count FROM borrow GROUP BY book_id ORDER BY count DESC LIMIT 5
    from sqlalchemy import func
    
    popular_books_query = db.session.query(
        Book.title,
        Book.author,
        func.count(Borrow.id).label('borrow_count')
    ).join(Borrow).group_by(Book.id).order_by(func.count(Borrow.id).desc()).limit(5).all()
    
    # En aktif 5 ogrenci
    active_students_query = db.session.query(
        Student.name,
        Student.student_number,
        func.count(Borrow.id).label('borrow_count')
    ).join(Borrow).group_by(Student.id).order_by(func.count(Borrow.id).desc()).limit(5).all()
    
    # Kategori bazli kitap dagilimi
    category_stats = db.session.query(
        Category.name,
        func.count(Book.id).label('book_count')
    ).outerjoin(Book).group_by(Category.id).all()
    
    # Bu ayki odunc sayisi
    from datetime import date
    first_day_of_month = date.today().replace(day=1)
    monthly_borrows = Borrow.query.filter(Borrow.borrow_date >= first_day_of_month).count()
    
    return render_template('admin/dashboard.html',
                          total_books=total_books,
                          total_categories=total_categories,
                          total_students=total_students,
                          total_reviews=total_reviews,
                          active_borrows=active_borrows,
                          overdue_borrows=overdue_borrows,
                          recent_books=recent_books,
                          recent_borrows=recent_borrows,
                          overdue_list=overdue_list,
                          popular_books=popular_books_query,
                          active_students=active_students_query,
                          category_stats=category_stats,
                          monthly_borrows=monthly_borrows)


@app.route('/admin/qrcode')
@login_required
def admin_qrcode():
    """QR Kod Sayfasi - Ag erisimi icin QR kod olusturur."""
    local_ip = get_local_ip()
    port = 5000
    url = f"http://{local_ip}:{port}"
    qr_base64 = generate_qr_code(url)
    return render_template('admin/qrcode.html', qr_base64=qr_base64, url=url, ip=local_ip, port=port)


# =============================================================================
# ADMIN - CSV EXPORT (VERI DISA AKTARMA)
# =============================================================================

@app.route('/admin/export/books')
@login_required
def export_books_csv():
    """
    Kitap Listesini CSV Olarak Indir
    Tum kitaplarin bilgilerini CSV formatinda disa aktarir.
    """
    # StringIO: Bellekte metin dosyasi olusturur
    output = StringIO()
    
    # CSV writer olustur
    writer = csv.writer(output)
    
    # Baslik satiri
    writer.writerow(['ID', 'Title', 'Author', 'Category', 'ISBN', 'Page Count', 
                     'Publish Year', 'Quantity', 'Available', 'Floor', 'Shelf', 'Created At'])
    
    # Kitaplari yaz
    books = Book.query.order_by(Book.title).all()
    for book in books:
        writer.writerow([
            book.id,
            book.title,
            book.author,
            book.category.name if book.category else '',
            book.isbn or '',
            book.page_count or '',
            book.publish_year or '',
            book.quantity,
            book.available,
            book.floor,
            book.shelf,
            book.created_at.strftime('%Y-%m-%d %H:%M')
        ])
    
    # Response olustur
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=books_export.csv'}
    )


@app.route('/admin/export/students')
@login_required
def export_students_csv():
    """
    Ogrenci Listesini CSV Olarak Indir
    Tum ogrencilerin bilgilerini CSV formatinda disa aktarir.
    """
    output = StringIO()
    writer = csv.writer(output)
    
    # Baslik satiri
    writer.writerow(['ID', 'Student Number', 'Name', 'Email', 'Phone', 'Department', 
                     'Total Borrows', 'Created At'])
    
    # Ogrencileri yaz
    students = Student.query.order_by(Student.name).all()
    for student in students:
        writer.writerow([
            student.id,
            student.student_number,
            student.name,
            student.email or '',
            student.phone or '',
            student.department or '',
            len(student.borrows),  # Toplam odunc sayisi
            student.created_at.strftime('%Y-%m-%d %H:%M')
        ])
    
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=students_export.csv'}
    )


@app.route('/admin/export/borrows')
@login_required
def export_borrows_csv():
    """
    Odunc Kayitlarini CSV Olarak Indir
    Tum odunc islemlerini CSV formatinda disa aktarir.
    """
    output = StringIO()
    writer = csv.writer(output)
    
    # Baslik satiri
    writer.writerow(['ID', 'Book Title', 'Student Name', 'Student Number', 
                     'Borrow Date', 'Due Date', 'Return Date', 'Status', 'Notes'])
    
    # Odunc kayitlarini yaz
    borrows = Borrow.query.order_by(Borrow.borrow_date.desc()).all()
    for borrow in borrows:
        writer.writerow([
            borrow.id,
            borrow.book.title,
            borrow.student.name,
            borrow.student.student_number,
            borrow.borrow_date.strftime('%Y-%m-%d'),
            borrow.due_date.strftime('%Y-%m-%d'),
            borrow.return_date.strftime('%Y-%m-%d') if borrow.return_date else '',
            borrow.status,
            borrow.notes or ''
        ])
    
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=borrows_export.csv'}
    )


# =============================================================================
# ADMIN - KITAP YONETIMI (CRUD)
# =============================================================================

@app.route('/admin/books')
@login_required
def admin_books():
    """Kitap Listesi - Arama ve sayfalama ile kitaplari gosterir."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    
    query = Book.query
    if search:
        query = query.filter((Book.title.ilike(f'%{search}%')) | (Book.author.ilike(f'%{search}%')))
    
    books = query.order_by(Book.created_at.desc()).paginate(page=page, per_page=10)
    return render_template('admin/books.html', books=books, search=search)


@app.route('/admin/books/add', methods=['GET', 'POST'])
@login_required
def admin_book_add():
    """Yeni Kitap Ekleme Formu ve Islemi"""
    if request.method == 'POST':
        # Form verilerini al
        title = request.form.get('title')
        author = request.form.get('author')
        description = request.form.get('description')
        category_id = request.form.get('category_id')
        isbn = request.form.get('isbn')
        page_count = request.form.get('page_count')
        publish_year = request.form.get('publish_year')
        quantity = request.form.get('quantity', 1)
        floor = request.form.get('floor', 1)
        shelf = request.form.get('shelf', 'A')
        
        # Resim yukleme
        image_path = None
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename and allowed_file(file.filename):
                # Guvenli dosya adi olustur
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                filename = f"{timestamp}_{filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_path = filename
        
        # Kitap olustur ve kaydet
        book = Book(
            title=title, author=author, description=description,
            category_id=category_id if category_id else None,
            isbn=isbn,
            page_count=int(page_count) if page_count else None,
            publish_year=int(publish_year) if publish_year else None,
            quantity=int(quantity), available=int(quantity),
            floor=int(floor) if floor else 1,
            shelf=shelf if shelf else 'A',
            image_path=image_path
        )
        db.session.add(book)
        db.session.commit()
        
        flash('Book added successfully!', 'success')
        return redirect(url_for('admin_books'))
    
    categories = Category.query.order_by(Category.name).all()
    return render_template('admin/book_form.html', book=None, categories=categories)


@app.route('/admin/books/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def admin_book_edit(id):
    """Kitap Duzenleme Formu ve Islemi"""
    book = Book.query.get_or_404(id)
    
    if request.method == 'POST':
        # Bilgileri guncelle
        book.title = request.form.get('title')
        book.author = request.form.get('author')
        book.description = request.form.get('description')
        book.category_id = request.form.get('category_id') or None
        book.isbn = request.form.get('isbn')
        book.page_count = int(request.form.get('page_count')) if request.form.get('page_count') else None
        book.publish_year = int(request.form.get('publish_year')) if request.form.get('publish_year') else None
        book.floor = int(request.form.get('floor')) if request.form.get('floor') else 1
        book.shelf = request.form.get('shelf') or 'A'
        
        # Stok guncelleme
        new_quantity = int(request.form.get('quantity', 1))
        diff = new_quantity - book.quantity
        book.quantity = new_quantity
        book.available = max(0, book.available + diff)
        
        # Yeni resim yuklendiyse
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename and allowed_file(file.filename):
                # Eski resmi sil
                if book.image_path:
                    old_path = os.path.join(app.config['UPLOAD_FOLDER'], book.image_path)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                
                # Yeni resmi kaydet
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                filename = f"{timestamp}_{filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                book.image_path = filename
        
        db.session.commit()
        flash('Book updated successfully!', 'success')
        return redirect(url_for('admin_books'))
    
    categories = Category.query.order_by(Category.name).all()
    return render_template('admin/book_form.html', book=book, categories=categories)


@app.route('/admin/books/delete/<int:id>', methods=['POST'])
@login_required
def admin_book_delete(id):
    """Kitap Silme Islemi"""
    book = Book.query.get_or_404(id)
    
    # Resim dosyasini sil
    if book.image_path:
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], book.image_path)
        if os.path.exists(image_path):
            os.remove(image_path)
    
    # Iliskili odunc kayitlarini sil
    Borrow.query.filter_by(book_id=id).delete()
    
    # Kitabi sil
    db.session.delete(book)
    db.session.commit()
    
    flash('Book deleted successfully!', 'success')
    return redirect(url_for('admin_books'))


# =============================================================================
# ADMIN - KATEGORI YONETIMI
# =============================================================================

@app.route('/admin/categories')
@login_required
def admin_categories():
    """Kategori Listesi"""
    categories = Category.query.order_by(Category.name).all()
    return render_template('admin/categories.html', categories=categories)


@app.route('/admin/categories/add', methods=['POST'])
@login_required
def admin_category_add():
    """Yeni Kategori Ekleme"""
    name = request.form.get('name')
    if name:
        # Ayni isimde kategori var mi kontrol et
        existing = Category.query.filter_by(name=name).first()
        if existing:
            flash('This category already exists!', 'warning')
        else:
            category = Category(name=name)
            db.session.add(category)
            db.session.commit()
            flash('Category added successfully!', 'success')
    return redirect(url_for('admin_categories'))


@app.route('/admin/categories/delete/<int:id>', methods=['POST'])
@login_required
def admin_category_delete(id):
    """Kategori Silme - Kitaplarin kategorisi NULL olur"""
    category = Category.query.get_or_404(id)
    
    # Bu kategorideki kitaplarin kategorisini NULL yap
    Book.query.filter_by(category_id=id).update({'category_id': None})
    
    db.session.delete(category)
    db.session.commit()
    
    flash('Category deleted successfully!', 'success')
    return redirect(url_for('admin_categories'))


# =============================================================================
# ADMIN - OGRENCI YONETIMI (CRUD)
# =============================================================================

@app.route('/admin/students')
@login_required
def admin_students():
    """Ogrenci Listesi - Arama ve sayfalama ile"""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    
    query = Student.query
    if search:
        query = query.filter((Student.name.ilike(f'%{search}%')) | (Student.student_number.ilike(f'%{search}%')))
    
    students = query.order_by(Student.name).paginate(page=page, per_page=10)
    return render_template('admin/students.html', students=students, search=search)


@app.route('/admin/students/add', methods=['GET', 'POST'])
@login_required
def admin_student_add():
    """Yeni Ogrenci Ekleme"""
    if request.method == 'POST':
        student_number = request.form.get('student_number')
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        department = request.form.get('department')
        
        # Ogrenci numarasi benzersiz olmali
        existing = Student.query.filter_by(student_number=student_number).first()
        if existing:
            flash('This student number is already registered!', 'warning')
            return redirect(url_for('admin_student_add'))
        
        student = Student(student_number=student_number, name=name, email=email, phone=phone, department=department)
        db.session.add(student)
        db.session.commit()
        
        flash('Student added successfully!', 'success')
        return redirect(url_for('admin_students'))
    
    return render_template('admin/student_form.html', student=None)


@app.route('/admin/students/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def admin_student_edit(id):
    """Ogrenci Duzenleme"""
    student = Student.query.get_or_404(id)
    
    if request.method == 'POST':
        new_number = request.form.get('student_number')
        
        # Numara degistiyse benzersizlik kontrolu
        if new_number != student.student_number:
            existing = Student.query.filter_by(student_number=new_number).first()
            if existing:
                flash('This student number belongs to another student!', 'warning')
                return redirect(url_for('admin_student_edit', id=id))
        
        student.student_number = new_number
        student.name = request.form.get('name')
        student.email = request.form.get('email')
        student.phone = request.form.get('phone')
        student.department = request.form.get('department')
        
        db.session.commit()
        flash('Student updated successfully!', 'success')
        return redirect(url_for('admin_students'))
    
    return render_template('admin/student_form.html', student=student)


@app.route('/admin/students/delete/<int:id>', methods=['POST'])
@login_required
def admin_student_delete(id):
    """Ogrenci Silme - Odunc ve yorum kayitlari da silinir"""
    student = Student.query.get_or_404(id)
    
    Borrow.query.filter_by(student_id=id).delete()
    Review.query.filter_by(student_id=id).delete()
    db.session.delete(student)
    db.session.commit()
    
    flash('Student deleted successfully!', 'success')
    return redirect(url_for('admin_students'))


@app.route('/admin/students/<int:id>/history')
@login_required
def admin_student_history(id):
    """Ogrenci Odunc Gecmisi"""
    student = Student.query.get_or_404(id)
    borrows = Borrow.query.filter_by(student_id=id).order_by(Borrow.borrow_date.desc()).all()
    return render_template('admin/student_history.html', student=student, borrows=borrows)


# =============================================================================
# ADMIN - ODUNC YONETIMI
# =============================================================================

@app.route('/admin/borrows')
@login_required
def admin_borrows():
    """Odunc Takip Listesi - Durum filtresi ile"""
    update_overdue_status()
    
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')
    
    query = Borrow.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    
    borrows = query.order_by(Borrow.created_at.desc()).paginate(page=page, per_page=10)
    return render_template('admin/borrows.html', borrows=borrows, status_filter=status_filter)


@app.route('/admin/borrows/add', methods=['GET', 'POST'])
@login_required
def admin_borrow_add():
    """Yeni Odunc Verme Islemi"""
    if request.method == 'POST':
        book_id = request.form.get('book_id')
        student_id = request.form.get('student_id')
        duration = int(request.form.get('duration', 14))  # Varsayilan 14 gun
        notes = request.form.get('notes')
        
        # Kitap musait mi kontrol et
        book = Book.query.get(book_id)
        if not book or book.available <= 0:
            flash('This book is currently not available!', 'danger')
            return redirect(url_for('admin_borrow_add'))
        
        # Odunc kaydini olustur
        borrow = Borrow(
            book_id=book_id, 
            student_id=student_id, 
            due_date=datetime.utcnow() + timedelta(days=duration), 
            notes=notes
        )
        
        # Musait sayiyi azalt
        book.available -= 1
        
        db.session.add(borrow)
        db.session.commit()
        
        flash('Book borrowed successfully!', 'success')
        return redirect(url_for('admin_borrows'))
    
    # Musait kitaplar ve tum ogrenciler
    books = Book.query.filter(Book.available > 0).order_by(Book.title).all()
    students = Student.query.order_by(Student.name).all()
    return render_template('admin/borrow_form.html', books=books, students=students)


@app.route('/admin/borrows/return/<int:id>', methods=['POST'])
@login_required
def admin_borrow_return(id):
    """Kitap Iade Islemi"""
    borrow = Borrow.query.get_or_404(id)
    
    if borrow.status in ['active', 'overdue']:
        borrow.status = 'returned'
        borrow.return_date = datetime.utcnow()
        borrow.book.available += 1  # Musait sayiyi artir
        db.session.commit()
        flash('Book returned successfully!', 'success')
    
    return redirect(url_for('admin_borrows'))


@app.route('/admin/borrows/extend/<int:id>', methods=['POST'])
@login_required
def admin_borrow_extend(id):
    """Odunc Suresini 7 Gun Uzatma"""
    borrow = Borrow.query.get_or_404(id)
    
    if borrow.status in ['active', 'overdue']:
        borrow.due_date = borrow.due_date + timedelta(days=7)
        
        # Eger gecikme durumundaysa ve yeni tarih gelecekteyse aktife cevir
        if borrow.status == 'overdue' and borrow.due_date > datetime.utcnow():
            borrow.status = 'active'
        
        db.session.commit()
        flash('Due date extended by 7 days!', 'success')
    
    return redirect(url_for('admin_borrows'))


# =============================================================================
# ADMIN - YORUM YONETIMI
# =============================================================================

@app.route('/admin/reviews')
@login_required
def admin_reviews():
    """Tum Yorumlari Listele"""
    page = request.args.get('page', 1, type=int)
    reviews = Review.query.order_by(Review.created_at.desc()).paginate(page=page, per_page=10)
    return render_template('admin/reviews.html', reviews=reviews)


@app.route('/admin/reviews/delete/<int:id>', methods=['POST'])
@login_required
def admin_review_delete(id):
    """Yorum Silme"""
    review = Review.query.get_or_404(id)
    db.session.delete(review)
    db.session.commit()
    flash('Review deleted successfully!', 'success')
    return redirect(url_for('admin_reviews'))


# =============================================================================
# HATA SAYFALARI
# =============================================================================

@app.errorhandler(404)
def not_found_error(error):
    """404 - Sayfa Bulunamadi Hatasi"""
    return render_template('errors/404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    """500 - Sunucu Hatasi"""
    db.session.rollback()  # Hata durumunda transaction'i geri al
    return render_template('errors/500.html'), 500


# =============================================================================
# VERITABANI BASLATMA
# =============================================================================

def init_db():
    """
    Veritabanini Baslat
    - Tablolari olusturur
    - Varsayilan admin hesabi ekler
    - Varsayilan kategorileri ekler
    """
    with app.app_context():
        # Tablolari olustur
        db.create_all()
        
        # Varsayilan admin hesabi (yoksa olustur)
        if not Admin.query.filter_by(username='admin').first():
            admin = Admin(username='admin')
            admin.set_password(os.environ.get('ADMIN_PASSWORD', 'admin123'))
            db.session.add(admin)
        
        # Varsayilan kategoriler (Ingilizce)
        default_categories = ['Adventure', 'History', 'Psychology', 'Science Fiction', 
                             'Novel', 'Philosophy', 'Science', 'Art', 'Biography', 'Children']
        
        for cat_name in default_categories:
            if not Category.query.filter_by(name=cat_name).first():
                db.session.add(Category(name=cat_name))
        
        db.session.commit()


# =============================================================================
# UYGULAMA BASLATMA
# =============================================================================

if __name__ == '__main__':
    # Gerekli klasorleri olustur
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Veritabanini baslat
    init_db()
    
    # Yerel IP adresini al
    local_ip = get_local_ip()
    
    # Baslangic mesajlari
    print("\n" + "="*50)
    print("LIBRARY MANAGEMENT SYSTEM")
    print("="*50)
    print(f"Local access:    http://127.0.0.1:5000")
    print(f"Network access:  http://{local_ip}:5000")
    print(f"Admin panel:     http://127.0.0.1:5000/admin")
    print("="*50)
    print("Default admin username: admin")
    print("Default admin password: value of ADMIN_PASSWORD, or admin123 if unset")
    print("="*50 + "\n")
    
    # Uygulamayi calistir
    # host='0.0.0.0': Tum ag arayuzlerinden erisime izin ver
    # port=5000: 5000 portunda calistir
    # debug=True: Hata ayiklama modu (gelistirme icin)
    app.run(host='0.0.0.0', port=5000, debug=True)
