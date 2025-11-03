from flask import Flask, render_template, request, jsonify, redirect, url_for
import sqlite3
from datetime import datetime
import os

app = Flask(__name__)
app.config['DATABASE'] = 'mahjong.db'

def get_db():
    """Connect to the database"""
    db = sqlite3.connect(app.config['DATABASE'])
    db.row_factory = sqlite3.Row
    return db

def init_db():
    """Initialize the database"""
    with app.app_context():
        db = get_db()
        
        # Create games table
        db.execute('''
            CREATE TABLE IF NOT EXISTS games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                player1_name TEXT NOT NULL,
                player1_score INTEGER NOT NULL,
                player1_points REAL NOT NULL,
                player2_name TEXT NOT NULL,
                player2_score INTEGER NOT NULL,
                player2_points REAL NOT NULL,
                player3_name TEXT NOT NULL,
                player3_score INTEGER NOT NULL,
                player3_points REAL NOT NULL,
                player4_name TEXT NOT NULL,
                player4_score INTEGER NOT NULL,
                player4_points REAL NOT NULL
            )
        ''')
        
        # Create players table
        db.execute('''
            CREATE TABLE IF NOT EXISTS players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Insert default players if they don't exist
        default_players = ['群主', 'Han', 'Henry', 'YHW']
        for player in default_players:
            try:
                db.execute('INSERT OR IGNORE INTO players (name) VALUES (?)', (player,))
            except:
                pass
        
        db.commit()
        db.close()

def calculate_points(scores):
    """
    Calculate points for each player based on Mahjong scoring rules.
    scores: list of tuples [(name, score), ...]
    Returns: list of tuples [(name, score, points), ...]
    """
    # Sort by score descending
    sorted_players = sorted(scores, key=lambda x: x[1], reverse=True)
    
    # Assign rank points
    rank_points = [15, 5, -5, -15]
    
    results = []
    for i, (name, score) in enumerate(sorted_players):
        # Calculate final points: rank_points + (score - 25000) / 1000
        points = rank_points[i] + (score - 25000) / 1000
        results.append((name, score, points))
    
    return results

@app.route('/')
def index():
    """Home page"""
    return render_template('index.html')

@app.route('/add_game')
def add_game():
    """Add game page"""
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT name FROM players ORDER BY name')
    players = [row['name'] for row in cursor.fetchall()]
    db.close()
    return render_template('add_game.html', players=players)

@app.route('/manage_players')
def manage_players():
    """Manage players page"""
    return render_template('manage_players.html')

@app.route('/calculate', methods=['POST'])
def calculate():
    """Calculate and store game results"""
    data = request.json
    
    # Validate inputs
    try:
        players = []
        for i in range(1, 5):
            name = data.get(f'player{i}_name', '').strip()
            score = int(data.get(f'player{i}_score', 0))
            
            if not name:
                return jsonify({'error': f'Player {i} name is required'}), 400
            
            if score % 100 != 0:
                return jsonify({'error': f'Player {i} score must be a multiple of 100'}), 400
            
            players.append((name, score))
        
        # Calculate points
        results = calculate_points(players)
        
        # Store in database
        db = get_db()
        cursor = db.cursor()
        cursor.execute('''
            INSERT INTO games (
                player1_name, player1_score, player1_points,
                player2_name, player2_score, player2_points,
                player3_name, player3_score, player3_points,
                player4_name, player4_score, player4_points
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            results[0][0], results[0][1], results[0][2],
            results[1][0], results[1][1], results[1][2],
            results[2][0], results[2][1], results[2][2],
            results[3][0], results[3][1], results[3][2]
        ))
        db.commit()
        game_id = cursor.lastrowid
        db.close()
        
        # Return results
        return jsonify({
            'success': True,
            'game_id': game_id,
            'results': [
                {'name': r[0], 'score': r[1], 'points': round(r[2], 1)}
                for r in results
            ]
        })
    
    except ValueError as e:
        return jsonify({'error': 'Invalid input. Please check all fields.'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/history')
def history():
    """View game history"""
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM games ORDER BY created_at DESC')
    games = cursor.fetchall()
    db.close()
    
    # Format games for template
    games_list = []
    for game in games:
        games_list.append({
            'id': game['id'],
            'created_at': game['created_at'],
            'players': [
                {
                    'name': game['player1_name'],
                    'score': game['player1_score'],
                    'points': round(game['player1_points'], 1)
                },
                {
                    'name': game['player2_name'],
                    'score': game['player2_score'],
                    'points': round(game['player2_points'], 1)
                },
                {
                    'name': game['player3_name'],
                    'score': game['player3_score'],
                    'points': round(game['player3_points'], 1)
                },
                {
                    'name': game['player4_name'],
                    'score': game['player4_score'],
                    'points': round(game['player4_points'], 1)
                }
            ]
        })
    
    return render_template('history.html', games=games_list)

@app.route('/calculate_totals', methods=['POST'])
def calculate_totals():
    """Calculate total points for selected games"""
    data = request.json
    game_ids = data.get('game_ids', [])
    
    if not game_ids:
        return jsonify({'error': 'No games selected'}), 400
    
    db = get_db()
    cursor = db.cursor()
    
    # Fetch selected games
    placeholders = ','.join('?' * len(game_ids))
    cursor.execute(f'SELECT * FROM games WHERE id IN ({placeholders})', game_ids)
    games = cursor.fetchall()
    db.close()
    
    # Calculate totals for each player
    player_totals = {}
    for game in games:
        for i in range(1, 5):
            name = game[f'player{i}_name']
            points = game[f'player{i}_points']
            
            if name not in player_totals:
                player_totals[name] = 0
            player_totals[name] += points
    
    # Sort by total points descending
    sorted_totals = sorted(player_totals.items(), key=lambda x: x[1], reverse=True)
    
    return jsonify({
        'totals': [
            {'name': name, 'total_points': round(points, 1)}
            for name, points in sorted_totals
        ]
    })

@app.route('/remove_games', methods=['POST'])
def remove_games():
    """Remove selected games from history"""
    data = request.json
    game_ids = data.get('game_ids', [])
    
    if not game_ids:
        return jsonify({'error': 'No games selected'}), 400
    
    try:
        db = get_db()
        cursor = db.cursor()
        
        # Delete selected games
        placeholders = ','.join('?' * len(game_ids))
        cursor.execute(f'DELETE FROM games WHERE id IN ({placeholders})', game_ids)
        db.commit()
        deleted_count = cursor.rowcount
        db.close()
        
        return jsonify({
            'success': True,
            'deleted_count': deleted_count,
            'message': f'Successfully removed {deleted_count} game(s) from history'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/players', methods=['GET'])
def get_players():
    """Get all players"""
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT id, name FROM players ORDER BY name')
    players = [{'id': row['id'], 'name': row['name']} for row in cursor.fetchall()]
    db.close()
    return jsonify({'players': players})

@app.route('/api/players', methods=['POST'])
def add_player():
    """Add a new player"""
    data = request.json
    name = data.get('name', '').strip()
    
    if not name:
        return jsonify({'error': 'Player name is required'}), 400
    
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('INSERT INTO players (name) VALUES (?)', (name,))
        db.commit()
        player_id = cursor.lastrowid
        db.close()
        
        return jsonify({'success': True, 'id': player_id, 'name': name})
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Player name already exists'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/players/<int:player_id>', methods=['DELETE'])
def delete_player(player_id):
    """Delete a player"""
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('DELETE FROM players WHERE id = ?', (player_id,))
        db.commit()
        db.close()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    init_db()
    # Run on all interfaces so it's accessible externally
    app.run(host='0.0.0.0', port=5000, debug=False)

