from flask import Flask, jsonify, request
import pymysql
import os

# Koneksi ke database yang baru
timeout = 10
connection_params = {
    "charset": "utf8mb4",
    "connect_timeout": timeout,
    "cursorclass": pymysql.cursors.DictCursor,
    "host": os.getenv("DB_HOST"),
    "password": os.getenv("DB_PASSWORD"),
    "port": int(os.getenv("DB_PORT", 3306)),  # default to 3306 if not set
    "user": os.getenv("DB_USER"),
    "database": os.getenv("DB_NAME"),
    "write_timeout": timeout,
}

app = Flask(__name__)

def get_db_connection():
    try:
        connection = pymysql.connect(**connection_params)
        return connection
    except pymysql.MySQLError as e:
        print(f'Terjadi kesalahan saat menghubungkan ke database: {e}')
        return None
        
@app.route('/')
def home():
    return 'Hello, World!'
    
@app.route('/get_answer', methods=['GET'])
def get_answer():
    try:
        question_id = request.args.get('id')
        answer = request.args.get('ans')
        if not question_id:
            return jsonify({"error": "question_id parameter is required"}), 400
        
        connection = get_db_connection()
        if connection is None:
            return jsonify({"error": "Database connection failed"}), 500

        cursor = connection.cursor()
        cursor.execute("SELECT question_id, answer, score FROM question_answers WHERE question_id = %s AND answer = %s", (question_id, answer))
        row = cursor.fetchone()
        cursor.close()
        connection.close()

        if row is None:
            return jsonify({
                "answer": "FALSE",
                "score": 0,
                }), 200
        
        result = {
            "answer": "TRUE",
            "score": row['score'],
        }
        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/get_question', methods=['GET'])
def get_question():
    try:
        uniq_value = request.args.get('usr')
        type_value = request.args.get('type')
        
        # Check if type parameter is provided
        if not type_value:
            return jsonify({"error": "type parameter is required"}), 400

        connection = get_db_connection()
        if connection is None:
            return jsonify({"error": "Database connection failed"}), 500

        cursor = connection.cursor()

        # Check if the provided type exists in the question_answers table
        cursor.execute(""" 
            SELECT 
                IF(
                    EXISTS (
                        SELECT 1 
                        FROM question_answers 
                        WHERE type = %s
                    ),
                    'TRUE',
                    'FALSE'
                ) AS is_type_exists;
        """, (type_value,))
        row = cursor.fetchone()

        # If the type doesn't exist, return an error message
        if row['is_type_exists'] == 'FALSE':
            cursor.close()
            connection.close()
            return jsonify({"message": "type yang anda masukan tidak ditemukan"}), 200

        # Check for incomplete questions for the given user and type
        cursor.execute("""
            SELECT 
                IF(
                    (SELECT COUNT(*) 
                    FROM question_answers qa
                    WHERE qa.type = %s) = 
                    (SELECT COUNT(*) 
                    FROM information_gathering ig 
                    WHERE ig.username = %s),
                    0,
                    (SELECT COUNT(*) 
                    FROM question_answers qa
                    WHERE qa.type = %s
                    AND qa.question_id NOT IN (
                        SELECT ig.question_id 
                        FROM information_gathering ig
                        WHERE ig.username = %s
                    ))
                ) AS incomplete_questions_count;
        """, (type_value, uniq_value, type_value, uniq_value))
        row = cursor.fetchone()

        # If no incomplete questions exist, return the message
        if row['incomplete_questions_count'] == 0:
            cursor.close()
            connection.close()
            return jsonify({"message": "Anda sudah mengerjakan semua"}), 200

        # Get the list of questions that the user has not answered
        cursor.execute("""
            SELECT qa.question_id, qa.question 
            FROM question_answers qa 
            LEFT JOIN information_gathering ig 
            ON qa.question_id = ig.question_id AND ig.username = %s 
            WHERE ig.question_id IS NULL AND qa.type = %s
        """, (uniq_value, type_value))
        
        rows = cursor.fetchall()
        cursor.close()
        connection.close()

        # If no questions are found, return an error message
        if not rows:
            return jsonify({"message": "No data found for the given type"}), 200

        # Prepare the result to return
        result = []
        for row in rows:
            result.append({
                "question_id": row['question_id'],
                "question": row['question'],
            })

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/insert_score', methods=['POST'])
def insert_score():
    data = request.get_json()
    
    username = data.get('username')
    question_id = data.get('id_question')
    score = data.get('score')
    
    connection = get_db_connection()
    if connection:
        try:
            cursor = connection.cursor()
            query = "INSERT INTO information_gathering (username, question_id, score) VALUES (%s, %s, %s)"
            cursor.execute(query, (username, question_id, score))
            connection.commit()
            return jsonify({"message": "Data inserted successfully"}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        finally:
            cursor.close()
            connection.close()
    else:
        return jsonify({"error": "Database connection failed"}), 500
    
@app.route('/get_version', methods=['GET'])
def get_version():
    try:
        connection = get_db_connection()
        if connection is None:
            return jsonify({"error": "Database connection failed"}), 500

        cursor = connection.cursor()
        cursor.execute("select * from app_version")
        row = cursor.fetchone()
        cursor.close()
        connection.close()

        if row is None:
            return jsonify({"error": "No data found for the given question_id"}), 404
        
        result = {
            "version": row['version'],
        }
        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/get_score', methods=['GET'])
def get_score():
    try:
        username = request.args.get('username')
        connection = get_db_connection()
        if connection is None:
            return jsonify({"error": "Database connection failed"}), 500

        cursor = connection.cursor()
        cursor.execute("SELECT SUM(COALESCE(score, 0)) AS total_score FROM information_gathering WHERE username = %s", (username,))
        row = cursor.fetchone()
        cursor.close()
        connection.close()

        total_score = row['total_score'] if row['total_score'] is not None else 0
        
        result = {
            "total_score": total_score,
        }
        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500
