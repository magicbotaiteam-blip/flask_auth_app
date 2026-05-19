import os

app_file = "/Users/siyang/flask_auth_app/app.py"
with open(app_file, "r") as f:
    lines = f.readlines()

main_idx = -1
for i, line in enumerate(lines):
    if line.strip() == 'if __name__ == "__main__":':
        main_idx = i
        break

if main_idx != -1:
    new_lines = lines[:main_idx]
    
    users_start = -1
    for i in range(main_idx, len(lines)):
        if '@app.route("/users")' in lines[i]:
            users_start = i - 1 # catch the blank line before it if any
            break
            
    if users_start != -1:
        new_lines.extend(lines[users_start:])
        new_lines.extend(lines[main_idx:users_start])
        
        with open(app_file, "w") as f:
            f.writelines(new_lines)
        print("Fixed routes order")
    else:
        print("Users route not found after main")
else:
    print("Main block not found")
