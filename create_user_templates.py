import os

TEMPLATE_DIR = "/Users/siyang/flask_auth_app/templates"

users_list_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Users - Magic Bot AI</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.8.1/font/bootstrap-icons.css">
</head>
<body class="bg-light">
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark mb-4">
        <div class="container">
            <a class="navbar-brand" href="/"><i class="bi bi-robot"></i> Magic Bot AI</a>
            <div class="collapse navbar-collapse">
                <ul class="navbar-nav me-auto">
                    <li class="nav-item"><a class="nav-link" href="/">Dashboard</a></li>
                </ul>
                <span class="navbar-text text-white">Admin: {{ username }}</span>
            </div>
        </div>
    </nav>

    <div class="container">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ 'success' if category == 'success' else 'danger' }}">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        <div class="d-flex justify-content-between align-items-center mb-4">
            <h2>User Management</h2>
            <div>
                <a href="/users/add" class="btn btn-primary"><i class="bi bi-person-plus"></i> Add User</a>
                <a href="/" class="btn btn-outline-secondary">Back to Dashboard</a>
            </div>
        </div>

        <div class="card shadow-sm">
            <div class="card-body p-0">
                <table class="table table-hover mb-0">
                    <thead class="table-light">
                        <tr>
                            <th>ID</th>
                            <th>Provider</th>
                            <th>Username</th>
                            <th>Email</th>
                            <th>Created At</th>
                            <th>Updated At</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for u in users %}
                        <tr>
                            <td><a href="/users/{{ u.id }}" class="fw-bold">{{ u.id }}</a></td>
                            <td><span class="badge bg-secondary">{{ u.provider }}</span></td>
                            <td>{{ u.username }}</td>
                            <td>{{ u.email or '-' }}</td>
                            <td>{{ u.created_at[:16] }}</td>
                            <td>{{ u.updated_at[:16] }}</td>
                        </tr>
                        {% else %}
                        <tr>
                            <td colspan="6" class="text-center py-4 text-muted">No users found.</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</body>
</html>
"""

user_detail_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>User Detail - Magic Bot AI</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.8.1/font/bootstrap-icons.css">
</head>
<body class="bg-light">
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark mb-4">
        <div class="container">
            <a class="navbar-brand" href="/"><i class="bi bi-robot"></i> Magic Bot AI</a>
            <div class="collapse navbar-collapse">
                <ul class="navbar-nav me-auto">
                    <li class="nav-item"><a class="nav-link" href="/">Dashboard</a></li>
                    <li class="nav-item"><a class="nav-link" href="/users">Users</a></li>
                </ul>
            </div>
        </div>
    </nav>

    <div class="container" style="max-width: 800px;">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ 'success' if category == 'success' else 'danger' }}">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        <div class="card shadow-sm mb-4">
            <div class="card-header bg-white py-3">
                <h4 class="mb-0">User Details: {{ user.username }}</h4>
            </div>
            <div class="card-body">
                <table class="table table-bordered">
                    <tbody>
                        <tr><th style="width: 30%">ID</th><td>{{ user.id }}</td></tr>
                        <tr><th>Provider</th><td><span class="badge bg-secondary">{{ user.provider }}</span></td></tr>
                        <tr><th>Provider ID</th><td>{{ user.provider_id or '-' }}</td></tr>
                        <tr><th>Username</th><td>{{ user.username }}</td></tr>
                        <tr><th>Email</th><td>{{ user.email or '-' }}</td></tr>
                        <tr><th>Role</th><td><span class="badge {{ 'bg-danger' if user_role == 'admin' else 'bg-primary' }}">{{ user_role }}</span></td></tr>
                        <tr><th>Created At</th><td>{{ user.created_at }}</td></tr>
                        <tr><th>Updated At</th><td>{{ user.updated_at }}</td></tr>
                    </tbody>
                </table>
            </div>
            <div class="card-footer bg-white py-3 d-flex justify-content-between">
                <div>
                    <a href="/users/{{ user.id }}/edit" class="btn btn-primary me-2"><i class="bi bi-pencil"></i> Edit User</a>
                    <a href="/users/{{ user.id }}/delete" class="btn btn-danger me-2" onclick="return confirm('Are you sure you want to delete this user?');"><i class="bi bi-trash"></i> Delete User</a>
                    <a href="/users/add" class="btn btn-success"><i class="bi bi-plus-circle"></i> Add User</a>
                </div>
                <a href="/users/{{ user.id }}/bots" class="btn btn-info text-white"><i class="bi bi-robot"></i> View User's Bots</a>
            </div>
        </div>
        
        <div class="text-center">
            <a href="/users" class="btn btn-outline-secondary me-2">Back to Users List</a>
            <a href="/" class="btn btn-outline-secondary">Back to Dashboard</a>
        </div>
    </div>
</body>
</html>
"""

user_form_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% if user %}Edit User{% else %}Add User{% endif %} - Magic Bot AI</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">
    <div class="container mt-5" style="max-width: 600px;">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ 'success' if category == 'success' else 'danger' }}">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        <div class="card shadow-sm">
            <div class="card-header bg-white">
                <h4 class="mb-0">{% if user %}Edit User: {{ user.username }}{% else %}Add New User{% endif %}</h4>
            </div>
            <div class="card-body">
                <form method="POST">
                    <div class="mb-3">
                        <label class="form-label">Username</label>
                        <input type="text" name="username" class="form-control" value="{{ user.username if user else '' }}" {% if user %}disabled{% endif %} required>
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Email</label>
                        <input type="email" name="email" class="form-control" value="{{ user.email if user else '' }}">
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Role</label>
                        <select name="role" class="form-select">
                            <option value="customer" {% if user_role == 'customer' %}selected{% endif %}>Customer</option>
                            <option value="admin" {% if user_role == 'admin' %}selected{% endif %}>Admin</option>
                        </select>
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Password {% if user %}<small class="text-muted">(Leave blank to keep unchanged)</small>{% endif %}</label>
                        <input type="password" name="password" class="form-control" {% if not user %}required{% endif %}>
                    </div>
                    
                    <div class="d-flex justify-content-between mt-4">
                        {% if user %}
                        <a href="/users/{{ user.id }}" class="btn btn-outline-secondary">Cancel</a>
                        {% else %}
                        <a href="/users" class="btn btn-outline-secondary">Cancel</a>
                        {% endif %}
                        <button type="submit" class="btn btn-primary">Save User</button>
                    </div>
                </form>
            </div>
        </div>
    </div>
</body>
</html>
"""

user_bots_list_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ user.username }}'s Bots - Magic Bot AI</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.8.1/font/bootstrap-icons.css">
</head>
<body class="bg-light">
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark mb-4">
        <div class="container">
            <a class="navbar-brand" href="/"><i class="bi bi-robot"></i> Magic Bot AI</a>
            <div class="collapse navbar-collapse">
                <ul class="navbar-nav me-auto">
                    <li class="nav-item"><a class="nav-link" href="/">Dashboard</a></li>
                    <li class="nav-item"><a class="nav-link" href="/users">Users</a></li>
                </ul>
            </div>
        </div>
    </nav>

    <div class="container">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <h2>Bots Created by {{ user.username }}</h2>
            <div>
                <a href="/users/{{ user.id }}" class="btn btn-outline-secondary me-2">Back to User Profile</a>
                <a href="/" class="btn btn-outline-secondary">Back to Dashboard</a>
            </div>
        </div>

        <div class="card shadow-sm">
            <div class="card-body p-0">
                <table class="table table-hover mb-0">
                    <thead class="table-light">
                        <tr>
                            <th>Bot ID</th>
                            <th>Name</th>
                            <th>Organization</th>
                            <th>Messaging</th>
                            <th>LLM</th>
                            <th>Created At</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for b in bots %}
                        <tr>
                            <td><a href="/register-bot/{{ b.id }}" class="fw-bold">{{ b.id }}</a></td>
                            <td>{{ b.name }}</td>
                            <td>{{ b.organization or '-' }}</td>
                            <td><span class="badge bg-secondary">{{ b.messaging or '-' }}</span></td>
                            <td>{{ b.llm or '-' }}</td>
                            <td>{{ b.created_at[:16] }}</td>
                        </tr>
                        {% else %}
                        <tr>
                            <td colspan="6" class="text-center py-4 text-muted">This user hasn't created any bots yet.</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</body>
</html>
"""

with open(os.path.join(TEMPLATE_DIR, "users_list.html"), "w") as f:
    f.write(users_list_html)

with open(os.path.join(TEMPLATE_DIR, "user_detail.html"), "w") as f:
    f.write(user_detail_html)

with open(os.path.join(TEMPLATE_DIR, "user_form.html"), "w") as f:
    f.write(user_form_html)

with open(os.path.join(TEMPLATE_DIR, "user_bots_list.html"), "w") as f:
    f.write(user_bots_list_html)

print("Templates created.")
