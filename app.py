from urllib import response
from flask import Flask, render_template, redirect, request, session, make_response,session,redirect
import spotipy
import spotipy.util as util

import os
from flask_session import Session
import uuid
# import credz.credz



import initial_fetch




app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('CLI_SECRET')
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = './.flask_session/'
Session(app)



caches_folder = './.spotify_caches/'
if not os.path.exists(caches_folder):
    os.makedirs(caches_folder)
def session_cache_path():
    return caches_folder + session.get('uuid')


@app.route('/')
def index():
    if not session.get('uuid'):
    # Step 1. Visitor is unknown, give random ID
        session['uuid'] = str(uuid.uuid4())

    cache_handler = spotipy.cache_handler.CacheFileHandler(cache_path=session_cache_path())
    auth_manager = spotipy.oauth2.SpotifyOAuth(scope="user-library-read",
                                               cache_handler=cache_handler,
                                               show_dialog=True)

    if request.args.get("code"):
        # Step 2. Being redirected from Spotify auth page
        auth_manager.get_access_token(request.args.get("code"))
        return redirect('/')

    if not auth_manager.validate_token(cache_handler.get_cached_token()):
        # Step 1. Display sign in link when no token
        auth_url = auth_manager.get_authorize_url()
        return render_template('index.html', authorization_url=auth_url, logged_in=False)
    # Step 3. Signed in, display data
    spotify = spotipy.Spotify(auth_manager=auth_manager)
    return render_template('index.html', authorization_url='/', logged_in=True)




@app.route('/fetch')
def go():
    cache_handler = spotipy.cache_handler.CacheFileHandler(cache_path=session_cache_path())
    auth_manager = spotipy.oauth2.SpotifyOAuth(cache_handler=cache_handler)
    if not auth_manager.validate_token(cache_handler.get_cached_token()):
        return redirect('/')

    spotify = spotipy.Spotify(auth_manager=auth_manager)
    
    try:
        spotify.me()
    except:
        return render_template('beta.html')

    print(f'Start fetch for {spotify.me()["display_name"]}')
    try:
        json_df, labels, values, rolling_window = initial_fetch.get_json(spotify_object=spotify)

        print(labels, values, '\n')
        print(f'Successful fetch for {spotify.me()["display_name"]}')

        session['periods_json'] = json_df
        session['labels'] = labels
        session['values'] = values
        session['rolling_window'] = rolling_window

        return redirect('/display_general')

        # return render_template('display.html', labels=labels, values=values)
    except Exception as e:
        print(e)



@app.route('/display_general')
def display_general():

    cache_handler = spotipy.cache_handler.CacheFileHandler(cache_path=session_cache_path())
    auth_manager = spotipy.oauth2.SpotifyOAuth(cache_handler=cache_handler)
    if not auth_manager.validate_token(cache_handler.get_cached_token()):
        return redirect('/')
    spotify = spotipy.Spotify(auth_manager=auth_manager)

    if(not (session.get('labels', None) and session.get('values', None))):
        return redirect('/fetch')

    labels = session.get('labels', None)
    values = session.get('values', None)
    rolling_window = session.get('rolling_window', None)
    return render_template('display_chart.html', labels=labels[rolling_window:], values=values[rolling_window:])

@app.route('/display_periods')
def display_periods():
    cache_handler = spotipy.cache_handler.CacheFileHandler(cache_path=session_cache_path())
    auth_manager = spotipy.oauth2.SpotifyOAuth(cache_handler=cache_handler)
    if not auth_manager.validate_token(cache_handler.get_cached_token()):
        return redirect('/')
    spotify = spotipy.Spotify(auth_manager=auth_manager)

    periods_json = session.get('periods_json')

    print(periods_json)
    labels = session.get('labels', None)
    values = session.get('values', None)
    l1 = list()
    l2 = list()
    for i in periods_json['song_start_index'].values():
        l1.append(i-3)
    for i in periods_json['song_end_index'].values():
        l2.append(i+3)
    new_list = list()
    new_list.append(l1)
    new_list.append(l2)
    values_n = list()
    labels_n = list()

    print(new_list)
    for i in range(len(new_list[0])):
        per_1 = list()
        per_1.append(values[new_list[0][i]:new_list[1][i]])
        values_n.append(per_1)
    for i in range(len(new_list[0])):
        per_2 = list()
        per_2.append(labels[new_list[0][i]:new_list[1][i]])
        labels_n.append(per_2)    


    return render_template('display_periods.html', periods_json=periods_json, labels=labels_n, values=values_n, list=new_list)

    


@app.route('/sign_out')
def sign_out():
    # session.pop("token_info", None)
    session.clear()
    return redirect('/')

    
    
























## fetch initial csv


##

if __name__ == '__main__':
    app.run(debug=True, threaded=True, port=int(os.environ.get("PORT",
                                                   os.environ.get("SPOTIPY_REDIRECT_URI", 8080).split(":")[-1])))