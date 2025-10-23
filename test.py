from db_connect import connection

cursor = connection.cursor()
cursor.execute("SELECT COUNT(*) FROM student")
print("Students in DB:", cursor.fetchone())