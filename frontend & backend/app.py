from flask import Flask, render_template, redirect, request, session, jsonify, make_response
import math
from requests import post, get
import requests
import urllib.parse
import datetime
import base64
import json
import random
#Importations

#We couldn't get the app.py to work in the backend folder, therefore the frontend folder contains
#the BACKEND app.py information.    

app = Flask(__name__, template_folder='templates', static_folder='static')
#Define app
app.secret_key = ''
SPOTIPY_CLIENT_ID = ''
SPOTIPY_CLIENT_SECRET = ''
SPOTIPY_REDIRECT_URI = 'http://127.0.0.1:5000/callback'
#Define authorization keys

AUTH_URL = 'https://accounts.spotify.com/authorize'
TOKEN_URL = 'https://accounts.spotify.com/api/token'
API_BASE_URL = 'https://api.spotify.com/v1/'
#Define base URLs for API

TICKETMASTER_API_KEY = ''
#Define Ticketmaster API key for events

def get_token():
    auth_string = SPOTIPY_CLIENT_ID + ':' + SPOTIPY_CLIENT_SECRET
    auth_bytes = auth_string.encode('utf-8')
    auth_base64 = str(base64.b64encode(auth_bytes), 'utf-8')

    url = 'https://accounts.spotify.com/api/token'
    headers = {
        'Authorization': 'Basic ' + auth_base64,
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    data = {'grant_type': 'client_credentials'}
    result = post(url, headers=headers, data=data)
    json_result = json.loads(result.content)
    token = json_result['access_token']
    return token

def get_auth_header(token):
    return {'Authorization': 'Bearer ' + token}

token = get_token()
def correct_songs_artists(token, song_titles):
    """Fixing titles for the search bar, for specific songs and returning formatted strings."""
    corrected_titles = []
    url = "https://api.spotify.com/v1/search"
    headers = get_auth_header(token)

    for song_title in song_titles:
        query = f"?q={song_title}&type=track&limit=1"
        query_url = url + query
        result = get(query_url, headers=headers)
        json_result = json.loads(result.content)["tracks"]["items"]
        if len(json_result) == 0:
            corrected_titles.append(None)
        else:
            song = json_result[0]['name']
            artist = json_result[0]['artists'][0]['name']
            corrected_titles.append(f"{song} - {artist}")

    return corrected_titles

def get_artist_id(token, artist_name):
    """Retrieve the artist ID given the artist name."""
    url = "https://api.spotify.com/v1/search"
    headers = get_auth_header(token)
    params = {
        "q": artist_name,
        "type": "artist",
        "limit": 1
    }
    
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    json_result = response.json()
    
    if 'artists' in json_result and json_result['artists']['items']:
        return json_result['artists']['items'][0]['id']
    
    return None

def correct_artist(token, artist_name):
    """Fix the name of a single artist for the search bar."""
    url = "https://api.spotify.com/v1/search"
    headers = get_auth_header(token)

    query = f"?q={artist_name}&type=artist&limit=1"
    query_url = url + query
    result = get(query_url, headers=headers)
    
    try:
        result.raise_for_status()
    except requests.exceptions.HTTPError as e:
        return None
    
    json_result = result.json().get("artists", {}).get("items", [])
    
    if len(json_result) == 0:
        return None
    else:
        return json_result[0]['name']

def search_for_specific_songs(token, specific_songs):
    """Find specific songs and return their information."""
    url = "https://api.spotify.com/v1/search"
    headers = get_auth_header(token)
    
    specific_song_ids = []
    
    for specific_song in specific_songs:
        query = f"track:{specific_song}"
        query_url = f"{url}?q={query}&type=track&limit=1"
        
        result = get(query_url, headers=headers)
        result.raise_for_status()
        json_result = result.json()
        
        if json_result['tracks']['items']:
            specific_song_ids.append(json_result['tracks']['items'][0]['id'])
    
    return specific_song_ids

def get_all_songs_of_artist(token, artist_name):
    """Retrieve all songs of a specific artist."""
    artist_id = get_artist_id(token, artist_name)
    if not artist_id:
        return {}

    url = f"https://api.spotify.com/v1/artists/{artist_id}/albums"
    headers = get_auth_header(token)
    query_params = {
        "include_groups": "album,single",
        "limit": 50
    }
    
    albums = []
    while url:
        result = requests.get(url, headers=headers, params=query_params)
        result.raise_for_status()
        json_result = result.json()
        albums.extend(json_result['items'])
        url = json_result['next']

    all_songs = {}
    for album in albums:
        album_id = album['id']
        album_name = album['name']
        album_url = f"https://api.spotify.com/v1/albums/{album_id}/tracks"
        all_songs[album_id] = []
        while album_url:
            album_result = requests.get(album_url, headers=headers)
            album_result.raise_for_status()
            album_tracks = album_result.json()
            for track in album_tracks['items']:
                all_songs[album_id].append(track['id'])
            album_url = album_tracks['next']
    
    return all_songs

def get_all_songs_of_multiple_artists(token, artist_names):
    """Retrieve all songs of multiple artists in a dictionary format."""
    all_songs = {}
    for artist_name in artist_names:
        artist_songs = get_all_songs_of_artist(token, artist_name)
        all_songs[artist_name] = artist_songs
    
    return all_songs

def get_song_details(token, track_ids):
    """Retrieve details of each track."""
    url = "https://api.spotify.com/v1/tracks"
    headers = get_auth_header(token)
    song_details = []
    batch_size = 50

    for i in range(0, len(track_ids), batch_size):
        batch = track_ids[i:i + batch_size]
        query_params = {
            "ids": ",".join(batch)
        }

        response = requests.get(url, headers=headers, params=query_params)
        response.raise_for_status()
        json_result = response.json()
        song_details.extend(json_result['tracks'])

    return song_details

def filter_songs(token, all_song_ids, exclude_explicit, decades):
    filtered_song_ids = {}

    all_song_details = {}
    for artist, albums in all_song_ids.items():
        all_song_details[artist] = {}
        for album_id, track_ids in albums.items():
            album_songs = get_song_details(token, track_ids)
            all_song_details[artist][album_id] = album_songs

    for artist, albums in all_song_details.items():
        filtered_tracks = {}
        
        for album_id, songs in albums.items():
            filtered_album_tracks = []

            for song in songs:
                track_id = song['id']
                # Filter explicit content
                if exclude_explicit and song.get('explicit'):
                    continue

                # Filter by decade
                if decades:
                    release_year = int(song['album']['release_date'][:4])
                    song_decade = (release_year // 10) * 10
                    if song_decade not in decades:
                        continue

                filtered_album_tracks.append(track_id)

            if filtered_album_tracks:
                filtered_tracks[album_id] = filtered_album_tracks

        if filtered_tracks:
            filtered_song_ids[artist] = filtered_tracks

    return filtered_song_ids

def filter_recommended_songs(token, track_ids, exclude_explicit, decades):
    filtered_track_ids = []

    # Get song details
    song_details = get_song_details(token, track_ids)

    for song in song_details:
        track_id = song['id']

        
        # Filter explicit content
        if exclude_explicit and song.get('explicit'):
            continue

        # Filter by decade
        if decades:
            release_year = int(song['album']['release_date'][:4])
            song_decade = (release_year // 10) * 10
            if song_decade not in decades:
                continue

        filtered_track_ids.append(track_id)

    return filtered_track_ids

def fetch_preferenced_songs(primitive_list, number_of_songs, filtered_all_song_ids, favourite_artists): 
    remaining_songs = number_of_songs - len(primitive_list)
    top_tracks = {}

    if remaining_songs > 0:
        divide_factor = 1 / (len(favourite_artists) + 1)
        amount_add = math.ceil(remaining_songs * divide_factor)
        
        for artist, albums in filtered_all_song_ids.items():
            all_tracks = []
            for track_ids in albums.values():
                all_tracks.extend(track_ids)
                random.shuffle(all_tracks)
                top_tracks[artist] = all_tracks

        selected_track_ids = []
        for artist, tracks in top_tracks.items():
            for track_id in tracks[:amount_add]:
                selected_track_ids.append(track_id)

        return selected_track_ids

    return []

def get_artist_ids(token, artist_names):
    """Get artist IDs for a list of artist names."""
    artist_ids = []
    for artist in artist_names:
        artist_id = get_artist_id(token, artist)
        if artist_id:
            artist_ids.append(artist_id)
    return artist_ids

def sort_playlist(playlist, preferred_sorting):
 
    if preferred_sorting in ["pop-H/L", "pop-L/H"]:
        sorted_playlist = sorted(
            playlist,
            key=lambda x: x.get('popularity', 0),
            reverse=(preferred_sorting == "pop-H/L")
        )
    elif preferred_sorting in ["rd-H/L", "rd-L/H"]:
        sorted_playlist = sorted(
            playlist,
            key=lambda x: x.get('release_date', ''),
            reverse=(preferred_sorting == "rd-H/L")
        )
    elif preferred_sorting in ["len-H/L", "len-L/H"]:
        sorted_playlist = sorted(
            playlist,
            key=lambda x: x.get('duration_ms', 0),
            reverse=(preferred_sorting == "len-H/L")
        )
    else:
        sorted_playlist = playlist

    return sorted_playlist


def get_recommended_songs(token: str, seed_artists: list, seed_genres: list, seed_tracks: list, limit: int = 50) -> list:
    """Retrieve recommended songs based on seeds and filters."""
    url = "https://api.spotify.com/v1/recommendations"
    headers = get_auth_header(token)
    
    genres = ["turkish", "hip-hop", "pop", "jazz", "house", "electronic", "reggae", "country", 
              "rock", "metal", "indie", "latin", "folk", "alternative", "punk", "techno", "classical"]

    # Check if all seed lists are empty
    if len(seed_artists) == 0 and  len(seed_genres) == 0 and len(seed_tracks) == 0:
        # If all seeds are empty, provide 3 random genres for randomness
        seed_genres = random.sample(genres, 3)

    # Limit the number of seed parameters
    seed_genres = seed_genres[:3]
    seed_artists = seed_artists[:2]
    max_tracks = 5 - len(seed_artists) - len(seed_genres)
    seed_tracks = seed_tracks[:max_tracks]
    seed_artist_ids = get_artist_ids(token, seed_artists)

    query_params = {
        "limit": limit,
        "seed_artists": ",".join(seed_artist_ids),
        "seed_genres": ",".join(seed_genres),
        "seed_tracks": ",".join(seed_tracks)
    }

    # Remove any empty parameters
    query_params = {k: v for k, v in query_params.items() if v}

    result = get(url, headers=headers, params=query_params)
    json_result = result.json()

    # Check if the response contains 'tracks'
    if 'tracks' not in json_result:
        print("Error: 'tracks' not found in the response")
        print(json_result)
        return []

    recommended_track_ids = [track['id'] for track in json_result['tracks']]
    
    return recommended_track_ids

def ensure_token_valid():
    if 'expires_at' in session and session['expires_at'] < datetime.datetime.now().timestamp():
        return redirect('/refresh-token')
    return None

@app.route('/correct-artist', methods=['POST'])
def correct_artist_route():
    token = get_token()
    data = request.get_json()
    artist_name = data.get('artist', '')
    corrected_name = correct_artist(token, artist_name)
    return jsonify({'corrected_name': corrected_name})

@app.route('/correct-song', methods=['POST'])
def correct_song_route():
    token = get_token()
    data = request.get_json()
    song_title = data.get('song', '')
    corrected_song = correct_songs_artists(token, [song_title])[0]
    return jsonify({'corrected_song': corrected_song})

@app.route('/generate-playlist', methods=['POST'])
def generate_playlist():
    token = get_token()
    data = request.json

    favourite_artists = data['artists']
    specific_songs = data['specific_songs']
    exclude_explicit = data['exclude_explicit']
    genres = data['genres']
    decades = data['decades']
    number_of_songs = data['number_of_songs']
    preferred_sorting = data['preferred_sorting']
    playlist_name = data['playlist_name'] if data['playlist_name'] else 'Playlist1'
    
    corrected_artists = [correct_artist(token, artist) for artist in favourite_artists if correct_artist(token, artist)]

    artist_ids = get_artist_ids(token, corrected_artists)

    primitive_list = search_for_specific_songs(token, specific_songs)
    
    all_song_ids = get_all_songs_of_multiple_artists(token, corrected_artists)
    
    filtered_songs = filter_songs(token, all_song_ids, exclude_explicit, decades)
    
    added_list = fetch_preferenced_songs(primitive_list, number_of_songs, filtered_songs, corrected_artists)
    
    list_for_recommend = primitive_list + added_list
    
    recommended_list = get_recommended_songs(token, artist_ids, genres, list_for_recommend)
    
    filtered_recommended_list = filter_recommended_songs(token, recommended_list, exclude_explicit, decades)
    
    remaining_songs = number_of_songs - len(added_list) - len(primitive_list)
    
    secondary_list = added_list + filtered_recommended_list[:remaining_songs]  
    
    shuffled_secondary_list = random.sample(secondary_list, len(secondary_list))
    
    final_playlist = primitive_list + shuffled_secondary_list

    final_playlist_details = get_song_details(token, final_playlist)
    
    formatted_playlist = [{
            'name': song['name'],
            'artist': song['artists'][0]['name'],
            'album': song['album']['name'],
            'duration': f"{song['duration_ms'] // 60000}:{(song['duration_ms'] % 60000) // 1000:02d}",
            'popularity': song.get('popularity', 0),
            'release_date': song['album'].get('release_date', ''),
            'duration_ms': song['duration_ms'],
            'url': song['external_urls']['spotify']
        } for song in final_playlist_details]

    sorted_playlist = sort_playlist(formatted_playlist, preferred_sorting)
        
    return jsonify({'playlist': sorted_playlist, 'playlist_name': playlist_name})

@app.route('/')
def home():
    '''
    function to send user to landing page
    returns: render_template of landing page
    '''
    
    return render_template('/landing-page.html')

@app.route('/login')
def login():
    '''
    function to authorize login
    returns: authorization url
    '''
    
    scope = 'user-read-private user-read-email user-top-read'
    #define scope of API
    params = {
        'client_id': SPOTIPY_CLIENT_ID,
        'response_type': 'code',
        'scope': scope,
        'redirect_uri': SPOTIPY_REDIRECT_URI,
        'show_dialog': True
    }
    #parameters
    auth_url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"
    #define the authorization url
    
    return redirect(auth_url)

@app.route('/logout')
def clear_cookie():
    """Clear session cookies and redirect to home."""
    response = make_response(redirect('/'))
    response.set_cookie('spotify_access_token', '', expires=0)
    session.pop('access_token', None)
    session.pop('refresh_token', None)
    session.pop('expires_at', None)
    return response

@app.route('/callback')
def callback():
    '''
    function for /callback after authorization
    returns: redirection to homepage afterwards
    '''
    if 'error' in request.args:
        return jsonify({'error': request.args['error']})
        #error handling
    if 'code' in request.args:
        req_body = {
            'grant_type': 'authorization_code',
            'code': request.args['code'],
            'redirect_uri': SPOTIPY_REDIRECT_URI,
            'client_id': SPOTIPY_CLIENT_ID,
            'client_secret': SPOTIPY_CLIENT_SECRET,
        }

        response = requests.post(TOKEN_URL, data=req_body)
        #get response via token
        token_info = response.json()
        #turn token info into json

        if 'access_token' not in token_info:
            return jsonify(token_info)
            # return the entire response for debugging

        session['access_token'] = token_info['access_token']
        session['refresh_token'] = token_info['refresh_token']
        session['expires_at'] = datetime.datetime.now().timestamp() + token_info['expires_in']
        #define session details (token etc.)

        return redirect('/')

@app.route('/refresh-token')
def refresh_token():
    '''
    function for refreshing token
    returns: redirection to home page
    '''
    if 'refresh_token' not in session:
        return redirect('/login')
        #if refresh token isn't found, redirect to login
    
    req_body = {
        'grant_type': 'refresh_token',
        'refresh_token': session['refresh_token'],
        'client_id': SPOTIPY_CLIENT_ID,
        'client_secret': SPOTIPY_CLIENT_SECRET,
    }

    response = requests.post(TOKEN_URL, data=req_body)
    #define response (token etc.)
    new_token_info = response.json()
    #turn token info into json

    if 'access_token' not in new_token_info:
        return jsonify(new_token_info)
        #return the entire response for debugging

    session['access_token'] = new_token_info['access_token']
    session['expires_at'] = datetime.datetime.now().timestamp() + new_token_info['expires_in']
    #define session info

    return redirect('/')

@app.route("/search", methods=['GET', 'POST'])
def search():
    '''
    function to get search
    returns: json version of recommendation data
    '''
    if 'access_token' not in session:
        return jsonify({'error': 'User not authenticated'}), 401

    if datetime.datetime.now().timestamp() > session.get('expires_at', 0):
        return jsonify({'error': 'Session expired'}), 401

    search_query = request.form.get('searchInput', '')
    search_type = request.form.get('searchType', '')
    #define search params

    if not search_query:
        return jsonify({'error': 'No search query provided'}), 400

    headers = {
        'Authorization': f'Bearer {session["access_token"]}'
    }
    #set authorization bearer

    if search_type == 'track':
    #condition for track search type
        try:
            
            search_url = f'{API_BASE_URL}search?q={urllib.parse.quote(search_query)}&type=track&limit=1'
            response = requests.get(search_url, headers=headers)
            response.raise_for_status()
            #get response

            search_results = response.json()
            #turn into json
            if 'tracks' in search_results and 'items' in search_results['tracks'] and len(search_results['tracks']['items']) > 0:
                track = search_results['tracks']['items'][0]
                song_id = track['id']

                recommendations_url = f'{API_BASE_URL}recommendations?seed_tracks={song_id}&limit=10'
                recommendations_response = requests.get(recommendations_url, headers=headers)
                recommendations_response.raise_for_status()
                #raise an exception for 4xx or 5xx status codes

                recommendations = recommendations_response.json()

                #extract details from recommendations
                recommended_songs = []
                for track in recommendations.get('tracks', []):
                    song_details = {
                        'track_name': track['name'],
                        'album_name': track['album']['name'],
                        'artist_name': ', '.join([artist['name'] for artist in track['artists']]),
                        'track_duration': track['duration_ms'],
                        'song_link': track['external_urls']['spotify']
                    }
                    recommended_songs.append(song_details)

                return jsonify({'song_id': song_id, 'recommended_songs': recommended_songs})

            else:
                return jsonify({'error': 'No track found in Spotify search'}), 404

        except requests.exceptions.RequestException as e:
            return jsonify({'error': f'Request failed: {str(e)}'}), 500

        except ValueError as e:
            return jsonify({'error': f'Error parsing response: {str(e)}'}), 500
    
    if search_type == 'artist':
        try:
            #perform Spotify API search to get the artist's ID
            search_url = f'{API_BASE_URL}search?q={urllib.parse.quote(search_query)}&type=artist&limit=1'
            response = requests.get(search_url, headers=headers)
            response.raise_for_status()

            search_results = response.json()
            if 'artists' in search_results and 'items' in search_results['artists'] and len(search_results['artists']['items']) > 0:
                artist = search_results['artists']['items'][0]
                artist_id = artist['id']

                #get related artists based on the artist ID
                related_artists_url = f'{API_BASE_URL}artists/{artist_id}/related-artists'
                related_artists_response = requests.get(related_artists_url, headers=headers)
                related_artists_response.raise_for_status()

                related_artists_data = related_artists_response.json()
                related_artists = []
                for related_artist in related_artists_data.get('artists', []):
                    related_artist_details = {
                        'name': related_artist['name'],
                        'genres': related_artist['genres'],
                    }
                    related_artists.append(related_artist_details)

                return jsonify({'artist_id': artist_id, 'related_artists': related_artists})

            else:
                return jsonify({'error': 'No artist found in Spotify search'}), 404

        except requests.exceptions.HTTPError as e:
            return jsonify({'error': f'Request failed: {str(e)}'}), 500

@app.route('/getstats')
def serve_stats_page():
    '''
    function to get stats of user
    returns: json information of top items of user
    '''
    if 'access_token' not in session:
        return redirect('/login')

    if datetime.datetime.now().timestamp() > session['expires_at']:
        return redirect('/refresh-token')

    headers = {
        'Authorization': f"Bearer {session['access_token']}"
    }

    time_range = request.args.get('time_range')
    limit = request.args.get('limit', 9)
    response = requests.get(API_BASE_URL + 'me/top/tracks', headers=headers, params={'time_range': time_range, 'limit': limit})
    tracks = response.json()
    #define and jsonify response

    track_info = []
    #initialize track info

    for track in tracks['items']:
        track_details = {
            'name': track['name'],
            'artists': ', '.join([artist['name'] for artist in track['artists']]),
            'song_link': track['external_urls']['spotify'],
            'album_cover': track['album']['images'][0]['url']
            }
        track_info.append(track_details)
        #add track with its properties to array

    return jsonify(track_info)

@app.route('/getartiststats')
def serve_stats_artist_page():
    '''
    function to get top artist stats of user
    '''

    if 'access_token' not in session:
        return redirect('/login')

    if datetime.datetime.now().timestamp() > session['expires_at']:
        return redirect('/refresh-token')

    headers = {
        'Authorization': f"Bearer {session['access_token']}"
    }
    
    response = requests.get(API_BASE_URL + 'me/top/artists', headers=headers, params={'limit': 10})
    artists = response.json()
    #define and jsonify response

    artist_info = []
    #initialize list

    for artist in artists['items']:
        artist_details = {
            'name': artist['name'],
            'popularity': artist['popularity'],
            'genres': artist['genres']
        }
        artist_info.append(artist_details)
        #add object with its properties to list

    return jsonify(artist_info)

@app.route('/getsongoftheday')
def songOTD():
    '''
    function to get the song of the day randomly via top tracks of user
    '''
    if 'access_token' in session:
        headers = {
            'Authorization': f"Bearer {session['access_token']}"
        }
        response = requests.get(API_BASE_URL + 'me/top/tracks', headers=headers, params={'limit': 50})
        
        if response.status_code == 200:
            top_tracks = response.json().get('items', [])
            if not top_tracks:
                return jsonify({'error': 'No top tracks found'}), 404
            
            random_index = random.randint(0, len(top_tracks) - 1)
            track = top_tracks[random_index]
            
            track_details = {
                'name': track['name'],
                'artists': ', '.join([artist['name'] for artist in track['artists']])
            }
            
            return jsonify(track_details)
        else:
            return jsonify({'error': 'Failed to fetch top tracks'}), response.status_code
    else:
        return jsonify({'error': 'No access token in session'}), 401
    
def returnOnlyArtists():
    '''
    function to extract only artist names from top artists of user
    returns: a list of user's top artist names
    '''
    topArtistNames = []
    headers = {
        'Authorization': f"Bearer {session['access_token']}"
    }
    response = requests.get(API_BASE_URL + 'me/top/artists', headers=headers, params={'limit': 10})
    artists = response.json()

    for artist in artists['items']:
        topArtistNames.append(artist['name'])

    return topArtistNames

@app.route('/artist-events')
def getArtistEvents():
    '''
    function to get events based on user's top artists
    returns: jsonified data of events of user's top artists
    '''
    API_KEY = TICKETMASTER_API_KEY
    url = 'https://app.ticketmaster.com/discovery/v2/events'
    artistEvents = []
    onlyArtists = returnOnlyArtists()
    
    for artist in onlyArtists:
        params = {
            'apikey': API_KEY,
            'keyword': artist  # Ensure this keyword matches exactly the artist's name
        }
        try:
            response = requests.get(url, params=params)
            events = response.json().get('_embedded', {}).get('events', [])

            # Filter events to only include those related to the exact artist
            filtered_events = [event for event in events if artist.lower() in event['name'].lower()]
            
            artistEvents.append({'artist': artist, 'events': filtered_events})
        except Exception as e:
            print(f"Error fetching events for artist '{artist}': {str(e)}")
            artistEvents.append({'artist': artist, 'events': []})  # Append empty events in case of error

    return jsonify(artistEvents)

@app.route('/location-events')
def get_events_nearby():
    '''
    function to get events based on a location (lat & long)
    returns: jsonified data of events near that location
    '''
    API_KEY = TICKETMASTER_API_KEY
    url = f'https://app.ticketmaster.com/discovery/v2/events'

    lat = request.args.get('lat')
    long = request.args.get('long')

    response = requests.get(url, params={'apikey':API_KEY, 'latlong':f'{lat},{long}', 'radius':'15', 'unit':'km'})
    events = response.json().get('_embedded', {}).get('events', [])
    return jsonify(events)

@app.route('/stats')
def statspage():
    '''
    function to send user to stats page
    returns: render template of stats page
    '''
    return render_template('stats-for-you.html')

@app.route('/music-game')
def musicgame():
    '''
    function to send user to music game page
    returns: render template of would you rather / music game
    '''
    return render_template('wouldyourather.html')

@app.route('/pl-gen')
def plgen():
    '''
    function to send user to playlist generator
    returns: render template of playlist generator
    '''
    return render_template('pl-generator.html')

@app.route('/faq')
def faq():
    '''
    function to send user to faq page
    returns: render template of faq
    '''
    return render_template('faq.html')

@app.route('/searchpage')
def searchpage():
    '''
    function to send user to search page
    returns: render template of search page
    '''
    return render_template('search-page.html')

@app.route('/upcoming-events')
def upcomingevents():
    '''
    function to send user to events page
    returns: render template of events page
    '''
    return render_template('upcoming-events.html')

if __name__ == '__main__':
    app.run(debug=True)
    #run app