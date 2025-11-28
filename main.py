from flask import Flask, render_template, request, redirect, flash, session
from flaskext.mysql import MySQL
from functools import wraps

app = Flask(__name__)
app.secret_key = 'rahasia'

db = MySQL(host="localhost", user="root", passwd="", db="db_pengaduan_masyarakat")
db.init_app(app)

# === Dekorator untuk proteksi login ===
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash("Silakan login terlebih dahulu.", "warning")
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function

# === ROUTE UMUM ===

from flask import render_template, session, redirect

@app.route('/')
def index():
    print("==> Akses ke / dengan session:", dict(session))
    if 'role' in session:
        print("==> Ditemukan role:", session['role'])
        if session['role'] == 'admin':
            return redirect('/admin/home')
        else:
            return redirect('/user/home')
    print("==> Menampilkan index.html")
    return render_template('index.html')



@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        cursor = db.get_db().cursor()
        cursor.execute("SELECT * FROM users WHERE username=%s AND password=%s", (username, password))
        data = cursor.fetchone()
        if data:
            session['user_id'] = data[0]  # id user
            session['user'] = data[1]     # username
            session['role'] = data[6]     # role

            # Redirect berdasarkan role
            if data[6] == 'admin':
                return redirect('/admin/home')
            else:
                return redirect('/user/home')
        else:
            flash('Username atau password salah!', 'danger')
            return redirect('/login')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        password_confirm = request.form['password_confirm']
        role = request.form['role']  # Ambil role dari form

        if password != password_confirm:
            flash('Konfirmasi password tidak cocok!', 'danger')
            return redirect('/register')

        cursor = db.get_db().cursor()
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        if cursor.fetchone():
            flash('Username sudah digunakan!', 'warning')
            return redirect('/register')

        cursor.execute("INSERT INTO users (username, password, role) VALUES (%s, %s, %s)", (username, password, role))
        db.get_db().commit()
        flash('Registrasi berhasil! Silakan login.', 'success')
        return redirect('/login')
    return render_template('register.html')

@app.route('/tentang')
def tentang():
    return render_template('user/tentang.html')


@app.route('/logout')
def logout():
    session.pop('user', None)
    session.pop('user_id', None)
    session.pop('role', None)
    return redirect('/login')

# === USER PANEL ===

@app.route('/user/home')
@login_required
def user_home():
    return render_template('user/home.html')

@app.route('/user/kirim-pengaduan', methods=['GET', 'POST'])
@login_required
def kirim_pengaduan():
    cursor = db.get_db().cursor()

    if request.method == 'POST':
        judul = request.form['judul']
        isi = request.form['isi']
        kategori_id = request.form['kategori_id']
        user_id = session['user_id']
        status = 'proses'

        try:
            cursor.execute(
                "INSERT INTO pengaduan (user_id, judul, isi_laporan, status, kategori_id) VALUES (%s, %s, %s, %s, %s)",
                (user_id, judul, isi, status, kategori_id)
            )
            db.get_db().commit()
            flash('Pengaduan berhasil dikirim.', 'success')
            return redirect('/user/riwayat')
        except Exception as e:
            flash(f'Terjadi kesalahan: {e}', 'danger')

    # Ambil semua kategori untuk ditampilkan di dropdown
    cursor.execute("SELECT id, nama_kategori FROM kategori_pengaduan")
    kategori_list = cursor.fetchall()

    return render_template('user/form_pengaduan.html', kategori_list=kategori_list)

@app.route('/user/riwayat')
@login_required
def riwayat_pengaduan():
    cursor = db.get_db().cursor()
    cursor.execute("""
    SELECT p.id, p.judul, p.isi_laporan, p.status, p.created_at, k.nama_kategori
    FROM pengaduan p
    LEFT JOIN kategori_pengaduan k ON p.kategori_id = k.id
    WHERE p.user_id = %s
    ORDER BY p.created_at DESC
""", (session['user_id'],))

    data = cursor.fetchall()
    return render_template('user/riwayat.html', pengaduan=data)

# === ADMIN PANEL ===

@app.route('/admin/home')
@login_required
def admin_home():
    if session.get('role') != 'admin':
        flash('Akses ditolak. Anda bukan admin.', 'danger')
        return redirect('/')

    cursor = db.get_db().cursor()

    cursor.execute("SELECT COUNT(*) FROM pengaduan")
    total_pengaduan = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM pengaduan WHERE status = 'proses'")
    proses = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM pengaduan WHERE status = 'pending'")
    pending = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM pengaduan WHERE status = 'Selesai'")
    selesai = cursor.fetchone()[0]

    cursor.execute("""
    SELECT u.username, p.judul, k.nama_kategori, p.status, p.created_at, p.isi_laporan
    FROM pengaduan p
    JOIN users u ON p.user_id = u.id
    LEFT JOIN kategori_pengaduan k ON p.kategori_id = k.id
    ORDER BY p.created_at DESC
    LIMIT 7
""")
    pengaduan_terbaru = cursor.fetchall()


    return render_template('admin/index.html',
                       total_pengaduan=total_pengaduan,
                       pending=pending,
                       proses=proses,
                       selesai=selesai,
                       pengaduan_terbaru=pengaduan_terbaru)


    

@app.route('/admin/daftar-pengaduan')
@login_required
def daftar_pengaduan():
    # Cek apakah user adalah admin
    if session.get('role') != 'admin':
        flash('Akses ditolak. Anda bukan admin.', 'danger')
        return redirect('/')

    # Ambil data pengaduan dari database, termasuk kategori
    cursor = db.get_db().cursor()
    cursor.execute("""
    SELECT p.id, u.username, p.judul, p.isi_laporan, p.created_at, p.status, k.nama_kategori
    FROM pengaduan p 
    JOIN users u ON p.user_id = u.id
    LEFT JOIN kategori_pengaduan k ON p.kategori_id = k.id
    ORDER BY p.created_at DESC
""")

    data = cursor.fetchall()

    # Kirim data ke template
    # Tampilkan di template admin/datapengaduan.html
    return render_template('admin/datapengaduan.html', hasil=data)

@app.route('/admin/hapus-pengaduan/<int:id>', methods=['POST'])
@login_required
def hapus_pengaduan(id):
    if session.get('role') != 'admin':
        flash('Akses ditolak. Anda bukan admin.', 'danger')
        return redirect('/')

    try:
        cursor = db.get_db().cursor()
        cursor.execute("DELETE FROM pengaduan WHERE id = %s", (id,))
        db.get_db().commit()
        flash("Pengaduan berhasil dihapus.", "success")
    except Exception as e:
        print("Terjadi kesalahan:", e)
        flash("Gagal menghapus pengaduan.", "danger")
    #ini terhubung dengan data yg ada di index adminya atau yg ada di rote daftar pengadaun
    return redirect('/admin/daftar-pengaduan')
@app.route("/admin/edit-pengaduan/<int:id>", methods=["GET", "POST"])
@login_required
def edit_pengaduan(id):
    if session.get('role') != 'admin':
        flash('Akses ditolak. Anda bukan admin.', 'danger')
        return redirect('/')

    cursor = db.get_db().cursor()

    if request.method == "POST":
        isi = request.form['isi']
        status = request.form['status']
        kategori_id = request.form['kategori_id']

        cursor.execute(
            "UPDATE pengaduan SET isi_laporan = %s, status = %s, kategori_id = %s WHERE id = %s",
            (isi, status, kategori_id, id)
        )
        db.get_db().commit()
        flash("Pengaduan berhasil diperbarui.", "success")
        return redirect("/admin/daftar-pengaduan")

    # Ambil data pengaduan
    cursor.execute("""
        SELECT p.id, u.username,p.judul, p.isi_laporan, p.kategori_id, p.status
        FROM pengaduan p
        JOIN users u ON p.user_id = u.id
        WHERE p.id = %s
    """, (id,))
    pengaduan = cursor.fetchone()

    # Ambil semua kategori
    cursor.execute("SELECT id, nama_kategori FROM kategori_pengaduan")
    kategori_list = cursor.fetchall()

    return render_template("admin/form_edit_pengaduan.html", pengaduan=pengaduan, kategori_list=kategori_list)


# === RUN ===
if __name__ == '__main__':
    app.run(debug=True)