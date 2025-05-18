from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import MySQLdb.cursors
import datetime

app = Flask(__name__)
app.config.from_object('config.Config')

mysql = MySQL(app)

# Decorator for requiring login
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'loggedin' not in session:
            flash('Please login to access this page.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Decorator for requiring admin role
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'loggedin' not in session or session.get('role') != 'admin':
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def home():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    # Fetch categories for filter dropdown
    cursor.execute("SELECT * FROM categories ORDER BY name")
    categories = cursor.fetchall()

    # Fetch posts
    category_filter = request.args.get('category_id')
    if category_filter:
        cursor.execute("""
            SELECT p.*, u.username AS author_username, c.name AS category_name 
            FROM posts p
            JOIN users u ON p.user_id = u.id
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE p.category_id = %s
            ORDER BY p.created_at DESC
        """, (category_filter,))
    else:
        cursor.execute("""
            SELECT p.*, u.username AS author_username, c.name AS category_name 
            FROM posts p
            JOIN users u ON p.user_id = u.id
            LEFT JOIN categories c ON p.category_id = c.id
            ORDER BY p.created_at DESC
        """)
    posts = cursor.fetchall()
    cursor.close()
    return render_template('home.html', posts=posts, categories=categories, current_category_id=category_filter)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        hashed_password = generate_password_hash(password)
        
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM users WHERE username = %s OR email = %s', (username, email))
        account = cursor.fetchone()
        
        if account:
            flash('Account already exists!', 'danger')
        elif not username or not email or not password:
            flash('Please fill out the form!', 'danger')
        else:
            cursor.execute('INSERT INTO users (username, email, password) VALUES (%s, %s, %s)', (username, email, hashed_password))
            mysql.connection.commit()
            flash('You have successfully registered!', 'success')
            return redirect(url_for('login'))
            
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
        account = cursor.fetchone()
        
        if account and check_password_hash(account['password'], password):
            session['loggedin'] = True
            session['id'] = account['id']
            session['username'] = account['username']
            session['role'] = account['role']
            flash('Logged in successfully!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Incorrect username/password!', 'danger')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('loggedin', None)
    session.pop('id', None)
    session.pop('username', None)
    session.pop('role', None)
    flash('You have successfully logged out.', 'success')
    return redirect(url_for('login'))

@app.route('/post/<int:post_id>')
def post(post_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    # Fetch the post
    cursor.execute("""
        SELECT p.*, u.username AS author_username, c.name AS category_name 
        FROM posts p
        JOIN users u ON p.user_id = u.id
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.id = %s
    """, (post_id,))
    post_data = cursor.fetchone()

    if not post_data:
        flash('Post not found!', 'danger')
        return redirect(url_for('home'))

    # Fetch comments for the post
    cursor.execute("""
        SELECT c.*, u.username AS author_username 
        FROM comments c
        JOIN users u ON c.user_id = u.id
        WHERE c.post_id = %s
        ORDER BY c.created_at ASC
    """, (post_id,))
    comments_data = cursor.fetchall()
    
    cursor.close()
    return render_template('post.html', post=post_data, comments=comments_data)

@app.route('/add_comment/<int:post_id>', methods=['POST'])
@login_required
def add_comment(post_id):
    if request.method == 'POST':
        content = request.form['comment_content']
        user_id = session['id']

        if not content:
            flash('Comment content cannot be empty.', 'danger')
            return redirect(url_for('post', post_id=post_id))

        cursor = mysql.connection.cursor()
        try:
            cursor.execute("INSERT INTO comments (content, user_id, post_id) VALUES (%s, %s, %s)", 
                           (content, user_id, post_id))
            mysql.connection.commit()
            flash('Comment added successfully!', 'success')
        except Exception as e:
            mysql.connection.rollback()
            flash(f'Error adding comment: {str(e)}', 'danger')
        finally:
            cursor.close()
    return redirect(url_for('post', post_id=post_id))

@app.route('/delete_comment/<int:comment_id>/<int:post_id>')
@login_required
def delete_comment(comment_id, post_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM comments WHERE id = %s", (comment_id,))
    comment = cursor.fetchone()

    if not comment:
        flash('Comment not found.', 'danger')
    elif comment['user_id'] != session['id'] and session.get('role') != 'admin':
        flash('You do not have permission to delete this comment.', 'danger')
    else:
        try:
            cursor.execute("DELETE FROM comments WHERE id = %s", (comment_id,))
            mysql.connection.commit()
            flash('Comment deleted successfully.', 'success')
        except Exception as e:
            mysql.connection.rollback()
            flash(f'Error deleting comment: {str(e)}', 'danger')
    cursor.close()
    
    # Redirect back to post page or admin panel based on 'from_admin' query param
    if request.args.get('from_admin'):
        return redirect(url_for('admin_panel', _anchor='comments')) # Go to comments tab
    return redirect(url_for('post', post_id=post_id))

@app.route('/create_post', methods=['GET', 'POST'])
@login_required
def create_post():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM categories ORDER BY name")
    categories = cursor.fetchall()

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        category_id = request.form['category_id']
        user_id = session['id']

        if not title or not content or not category_id:
            flash('Please fill all fields.', 'danger')
        else:
            try:
                cursor.execute("INSERT INTO posts (title, content, user_id, category_id) VALUES (%s, %s, %s, %s)",
                               (title, content, user_id, category_id))
                mysql.connection.commit()
                flash('Post created successfully!', 'success')
                return redirect(url_for('home'))
            except Exception as e:
                mysql.connection.rollback()
                flash(f'Error creating post: {str(e)}', 'danger')
    
    cursor.close()
    return render_template('create_post.html', categories=categories)

@app.route('/edit_post/<int:post_id>', methods=['GET', 'POST'])
@login_required
def edit_post(post_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    # Fetch the post
    cursor.execute("SELECT * FROM posts WHERE id = %s", (post_id,))
    post_data = cursor.fetchone()

    if not post_data:
        flash('Post not found!', 'danger')
        cursor.close()
        return redirect(url_for('home'))

    # Check permission
    if post_data['user_id'] != session['id'] and session.get('role') != 'admin':
        flash('You do not have permission to edit this post.', 'danger')
        cursor.close()
        return redirect(url_for('post', post_id=post_id))

    # Fetch categories
    cursor.execute("SELECT * FROM categories ORDER BY name")
    categories = cursor.fetchall()

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        category_id = request.form['category_id']

        if not title or not content or not category_id:
            flash('Please fill all fields.', 'danger')
        else:
            try:
                cursor.execute("""
                    UPDATE posts SET title = %s, content = %s, category_id = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (title, content, category_id, post_id))
                mysql.connection.commit()
                flash('Post updated successfully!', 'success')
                return redirect(url_for('post', post_id=post_id))
            except Exception as e:
                mysql.connection.rollback()
                flash(f'Error updating post: {str(e)}', 'danger')
    
    cursor.close()
    return render_template('edit_post.html', post=post_data, categories=categories)

@app.route('/delete_post/<int:post_id>')
@login_required
def delete_post(post_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT user_id FROM posts WHERE id = %s", (post_id,))
    post = cursor.fetchone()

    if not post:
        flash('Post not found.', 'danger')
    elif post['user_id'] != session['id'] and session.get('role') != 'admin':
        flash('You do not have permission to delete this post.', 'danger')
    else:
        try:
            cursor.execute("DELETE FROM posts WHERE id = %s", (post_id,))
            mysql.connection.commit()
            flash('Post deleted successfully.', 'success')
        except Exception as e:
            mysql.connection.rollback()
            flash(f'Error deleting post: {str(e)}', 'danger')
    cursor.close()
    # If admin deleted, redirect to admin panel posts tab
    if session.get('role') == 'admin' and request.referrer and 'admin' in request.referrer:
         return redirect(url_for('admin_panel', _anchor='posts'))
    return redirect(url_for('home'))

@app.route('/admin')
@login_required
@admin_required
def admin_panel():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    # Fetch all posts
    cursor.execute("""
        SELECT p.*, u.username AS author_username, c.name AS category_name 
        FROM posts p
        JOIN users u ON p.user_id = u.id
        LEFT JOIN categories c ON p.category_id = c.id
        ORDER BY p.created_at DESC
    """)
    posts = cursor.fetchall()

    # Fetch all users
    cursor.execute("SELECT * FROM users ORDER BY created_at DESC")
    users = cursor.fetchall()

    # Fetch all comments
    cursor.execute("""
        SELECT comm.*, u.username AS author_username, p.title AS post_title
        FROM comments comm
        JOIN users u ON comm.user_id = u.id
        JOIN posts p ON comm.post_id = p.id
        ORDER BY comm.created_at DESC
    """)
    comments = cursor.fetchall()

    # Fetch all categories
    cursor.execute("SELECT * FROM categories ORDER BY name")
    categories_list = cursor.fetchall()
    
    cursor.close()
    return render_template('admin_panel.html', posts=posts, users=users, comments=comments, categories_list=categories_list)

@app.route('/admin/user/role/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def admin_update_user_role(user_id):
    new_role = request.form.get('role')
    if not new_role or new_role not in ['user', 'admin']:
        flash('Invalid role specified.', 'danger')
        return redirect(url_for('admin_panel', _anchor='users'))

    cursor = mysql.connection.cursor()
    try:
        # Prevent last admin from being demoted
        if new_role == 'user':
            cursor.execute("SELECT COUNT(*) as admin_count FROM users WHERE role = 'admin'")
            admin_count = cursor.fetchone()[0]
            cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
            current_role = cursor.fetchone()[0]
            if admin_count <= 1 and current_role == 'admin':
                flash('Cannot remove the last administrator.', 'danger')
                return redirect(url_for('admin_panel', _anchor='users'))
        
        cursor.execute("UPDATE users SET role = %s WHERE id = %s", (new_role, user_id))
        mysql.connection.commit()
        flash('User role updated successfully.', 'success')
    except Exception as e:
        mysql.connection.rollback()
        flash(f'Error updating user role: {str(e)}', 'danger')
    finally:
        cursor.close()
    return redirect(url_for('admin_panel', _anchor='users'))

@app.route('/admin/user/delete/<int:user_id>')
@login_required
@admin_required
def admin_delete_user(user_id):
    if session['id'] == user_id:
        flash('You cannot delete yourself.', 'danger')
        return redirect(url_for('admin_panel', _anchor='users'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        # Check if the user is the last admin
        cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
        user_to_delete = cursor.fetchone()
        if user_to_delete and user_to_delete['role'] == 'admin':
            cursor.execute("SELECT COUNT(*) as admin_count FROM users WHERE role = 'admin'")
            admin_count = cursor.fetchone()['admin_count']
            if admin_count <= 1:
                flash('Cannot delete the last administrator.', 'danger')
                cursor.close()
                return redirect(url_for('admin_panel', _anchor='users'))

        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        mysql.connection.commit()
        flash('User deleted successfully.', 'success')
    except Exception as e:
        mysql.connection.rollback()
        flash(f'Error deleting user: {str(e)}', 'danger')
    finally:
        cursor.close()
    return redirect(url_for('admin_panel', _anchor='users'))

@app.route('/admin/category/add', methods=['POST'])
@login_required
@admin_required
def admin_add_category():
    category_name = request.form.get('category_name')
    if not category_name:
        flash('Category name cannot be empty.', 'danger')
        return redirect(url_for('admin_panel', _anchor='categories'))

    cursor = mysql.connection.cursor()
    try:
        cursor.execute("INSERT INTO categories (name) VALUES (%s)", (category_name,))
        mysql.connection.commit()
        flash('Category added successfully.', 'success')
    except MySQLdb.IntegrityError: # Handles unique constraint violation
        mysql.connection.rollback()
        flash('Category name already exists.', 'danger')
    except Exception as e:
        mysql.connection.rollback()
        flash(f'Error adding category: {str(e)}', 'danger')
    finally:
        cursor.close()
    return redirect(url_for('admin_panel', _anchor='categories'))

@app.route('/admin/category/edit/<int:category_id>', methods=['POST'])
@login_required
@admin_required
def admin_edit_category(category_id):
    new_category_name = request.form.get('new_category_name')
    if not new_category_name:
        flash('New category name cannot be empty.', 'danger')
        return redirect(url_for('admin_panel', _anchor='categories'))

    cursor = mysql.connection.cursor()
    try:
        cursor.execute("UPDATE categories SET name = %s WHERE id = %s", (new_category_name, category_id))
        mysql.connection.commit()
        flash('Category updated successfully.', 'success')
    except MySQLdb.IntegrityError:
        mysql.connection.rollback()
        flash('Another category with this name already exists.', 'danger')
    except Exception as e:
        mysql.connection.rollback()
        flash(f'Error updating category: {str(e)}', 'danger')
    finally:
        cursor.close()
    return redirect(url_for('admin_panel', _anchor='categories'))

@app.route('/admin/category/delete/<int:category_id>')
@login_required
@admin_required
def admin_delete_category(category_id):
    cursor = mysql.connection.cursor()
    try:
        # ON DELETE SET NULL is handled by DB, just delete the category
        cursor.execute("DELETE FROM categories WHERE id = %s", (category_id,))
        mysql.connection.commit()
        flash('Category deleted successfully. Posts in this category have had their category removed.', 'success')
    except Exception as e:
        mysql.connection.rollback()
        flash(f'Error deleting category: {str(e)}', 'danger')
    finally:
        cursor.close()
    return redirect(url_for('admin_panel', _anchor='categories'))

# Add a helper for strftime in Jinja2 if not already available by default
@app.context_processor
def inject_utilities():
    def format_dt(value, fmt='%Y-%m-%d %H:%M'):
        if value is None:
            return ""
        return value.strftime(fmt)
    
    return dict(
        format_datetime=format_dt,
        current_year=datetime.datetime.now().year
    )

if __name__ == '__main__':
    app.run(debug=True) 