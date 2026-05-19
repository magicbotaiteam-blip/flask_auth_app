grep -rl "$1" * |grep -v pycache |xargs sed -i '' 's/$1/$2/g'
