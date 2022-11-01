from time import time
from tracemalloc import start
import pandas as pd
import numpy as np
import math 
import os

import json



# import matplotlib.pyplot as plt
# import matplotlib.dates as mdates

# import seaborn as sns
# sns.set(style='darkgrid')

# %matplotlib inline
# # %matplotlib widget

from datetime import datetime

# from statsmodels.tsa.seasonal import seasonal_decompose
from cydets.algorithm import detect_cycles
# from scipy import signal





def createArray(name):
    name = []
    return name


def fetch_saved_tracks(spotify_object, limit=5, offset=0):
    result = spotify_object.current_user_saved_tracks(limit=limit, offset=offset)

    saved_tracks = result['items']
    playlist_size = result['total']

    saved_tracks_modified = []

    for idx, item in enumerate(saved_tracks):
        artist_temp = []

        for key in ['album', 'available_markets', 'disc_number', 'external_ids', 'external_urls', 'preview_url', 'type', 'href', 'track_number']:
            item['track'].pop(key)
        for idx, artist in enumerate(item['track']['artists']):
            for key in ['external_urls', 'href', 'id', 'type', 'uri']:
                artist.pop(key)

            artist_temp.append(artist['name'])
            item['track']['artists'] = artist_temp

        saved_tracks_modified.append(item)

    saved_tracks_dict = {
        'added_at': [],
        'artists': []
    }


    for idx, track in enumerate(saved_tracks_modified):

        saved_tracks_dict['artists'].append(track['track']['artists'])
        

        for key in track['track'].keys():
            
            if key not in saved_tracks_dict:
                key_arr = createArray(key)
                key_arr.append(track['track'][key])
                saved_tracks_dict[key] = key_arr
            else:
                if key != 'artists':
                    saved_tracks_dict[key] = np.concatenate((saved_tracks_dict[key], track['track'][key]), axis=None)

       
        saved_tracks_dict['added_at'].append(track['added_at'])


    dataframe = pd.DataFrame(data=saved_tracks_dict, columns=saved_tracks_dict.keys())

    dataframe['artists'] = dataframe['artists'].astype(str)

    dataframe['artists'] = dataframe['artists'].apply(lambda x: x.replace('[', ''))
    dataframe['artists'] = dataframe['artists'].apply(lambda x: x.replace(']', ''))

    
    # dataframe.to_csv("liked_songs.csv", index=False)
    return dataframe, playlist_size

def fetch_audio_features(spotify_object, df_to_concat, uri=['spotify:track:6q6rs0RG7nqU3lZaVwcxSf']):
    af = spotify_object.audio_features(tracks=uri)
    audio_features = {

    }
    

    for idx, track in enumerate(af):
        for key in track.keys():
            if key in ['id', 'uri', 'duration_ms', 'type', 'track_href']:
                continue
            elif key not in audio_features:
                key_arr = createArray(key)
                key_arr.append(track[key])
                audio_features[key] = key_arr
            else:
                audio_features[key] = np.concatenate((audio_features[key], track[key]), axis=None)

    dataframe = pd.DataFrame(data=audio_features, columns=audio_features.keys())
    dataframe_new = dataframe.join(df_to_concat, lsuffix='l', rsuffix='r')
    # dataframe_new.to_csv("audio_features.csv", index=False)
    return dataframe_new

def mergeArrays(spotify_object, df_previous, n_repetitions, rem, counter=1):
    if counter >= n_repetitions+1:
        df_no_features, size1 = fetch_saved_tracks(spotify_object, rem, counter * 50)
        df_new_features = fetch_audio_features(spotify_object, df_no_features, df_no_features['id'].to_numpy())
        df_new = pd.concat([df_previous, df_new_features])
        
        # df_new.to_csv("liked_tracks.csv", index=False)


        print(f'   iter --- {counter} --- finished')

        return df_new

    else:
        df_no_features, size1 = fetch_saved_tracks(spotify_object, 50, counter * 50)
        df_new_features = fetch_audio_features(spotify_object, df_no_features, df_no_features['id'].to_numpy())
        df_new = pd.concat([df_previous, df_new_features])
        # df_new.to_csv("liked_tracks.csv", index=False)
        print(f'   iter --- {counter}')

        return mergeArrays(spotify_object, df_new, n_repetitions, counter=counter+1, rem=rem)

 
    



def fetch_liked_tracks(spotify_object):
    df, size = fetch_saved_tracks(spotify_object, 50)
    df = fetch_audio_features(spotify_object, df, df['id'].to_numpy())
    print(f'\nINIT ARRAY CREATED {spotify_object.me()}\n')


    rem = (size - 50)%50
    n_repetitions = math.floor((size - 50)/50) 

    print(f'\nMERGE_ARRAYS START\n')
    df = mergeArrays(spotify_object, df, n_repetitions=n_repetitions, rem=rem)
    print(f'\nMERGE_ARRAYS FINISH\n')

    return df






def plot_time_series(col_names, title, rolling_window_days, df):
    



    # ax.locator_params(axis='x', tight=True)
    # plt.locator_params(axis='x', nbins=1, tight=True)

    for idx, col_name in enumerate(col_names):
        daily_series = pd.Series(data=np.array(df[col_name]), 
                                        name=col_name, 
                                        index=df['playlist_place']).sort_index()





    return daily_series.rolling(window = rolling_window_days).mean()



def process_cycles(cycles, duration_lowprecut, duration_lowcut, n_std, duration_upcut=10000):
    cycles = cycles.loc[cycles['duration'] > duration_lowprecut]

    print('initial len() {}'.format(len(cycles)))
    mean = np.mean(cycles['duration'], axis=0)
    sd = np.std(cycles['duration'], axis=0)

    cycles_outliered = [cycles.iloc[i] for i in range(len(cycles)) if (cycles.iloc[i]['duration'] < mean + (n_std * sd)) and (cycles.iloc[i]['duration'] > mean - (n_std * sd))]
    cycles_outliered_df = pd.DataFrame(cycles_outliered)


    # fig, ax = plt.subplots(figsize=(40, 5))

    # cycles['duration'].plot(kind='kde')
    # cycles_outliered_df['duration'].plot(kind='kde')

    cycl = cycles_outliered_df.loc[cycles_outliered_df['duration'] > duration_lowcut]
    cycl = cycl.loc[cycl['duration'] < duration_upcut]

    print('final len() {}'.format(len(cycl)))
    return cycl

def format_date(x):

    d_1 = datetime.strptime(x, '%Y-%m-%dT%H:%M:%SZ')
    d_2 = f'{d_1.day} of {d_1.strftime("%B")}, {d_1.year}'
    return d_2


def get_json(spotify_object, rolling_window=60):
    df = fetch_liked_tracks(spotify_object=spotify_object)
    print(f'\nDF FOR {spotify_object.me()} fed in, start processing\n')

    df.reset_index(inplace=True)
    # df.to_csv('qrgqegqwrg.csv')
    if df.shape[0] < 150:
        raise ValueError("Too short")
    elif df.shape[0] > 1000:
        rolling_window = 100
    else:
        rolling_window = 60


    ## initial data formatting
    df['playlist_place'] = np.flip(np.arange(0, len(df)))
    ##
    columns_to_drop = ['analysis_url', 'is_local', 'uri']
    df.drop(columns_to_drop, axis=1, inplace=True)

    df['explicit'].replace({
        True: 1,
        False: 0
    }, inplace=True)

    df['explicit'] = df['explicit'].astype(int)
    ##
    to_datetime = pd.to_datetime(df['added_at'])
    ##
    df['popularity'] = df['popularity']/100
    ##
    df.sort_values('playlist_place', ascending=True, inplace=True)
    df.set_index('playlist_place')

    print(f'\ntime series for {spotify_object.me()} start,\n ROLLING WINDOW = {rolling_window}\n')
    time_series = plot_time_series(['valence'], 'Valence over time (window = {} days)'.format(rolling_window), rolling_window, df)
    print(f'\ntime series for {spotify_object.me()} end\n')


    print(f'\npreprocessing cycles for {spotify_object.me()}\n')
    cycles = detect_cycles(time_series, drop_zero_docs=True)
    print(f'\nprecycles retrieved for {spotify_object.me()}\n')

    cycles.dropna(inplace=True)
    cycles.sort_values('doc', inplace=True, ascending=False)
    top_cycles = cycles[:10]


    dates_series = pd.Series(df['added_at'])
    dates_df = pd.DataFrame(dates_series)


    df_ma = pd.concat([dates_df, pd.DataFrame(time_series)], axis=1, join='outer')
    df_ma.set_index('added_at', inplace=True)
    df_ma['valence'] = df_ma['valence'].values[::-1]
    df_ma
    ma_series = df_ma.squeeze()

    print(f'\nprocessing cycles for {spotify_object.me()}\n')
    cycl = process_cycles(cycles=cycles, duration_lowprecut=5, duration_lowcut=20, n_std=40)
    print(f'\ncycles retrieved for {spotify_object.me()}\n')

    cycl = cycl.sort_values('doc', ascending=False)[:10] ######################

    for col in cycl.columns:
        if(col != 'doc'):
            cycl[col] = cycl[col].astype(int)

    df_new = pd.DataFrame(columns=['start_date', 'end_date', 'min_date', 'duration_days', 'duration_entries', 'cycle_depth', 'song_start_name', 'song_end_name', 'song_min_name', 'song_start_uri', 'song_min_uri', 'song_end_uri', 'song_start_index', 'song_end_index'])


    i = 0
    for index in cycl.index:
        # df rows
        song_start = df.iloc[int(cycl.loc[index]['t_start'])]
        song_end = df.iloc[int(cycl.loc[index]['t_end'])]

        song_min = df.iloc[int(cycl.loc[index]['t_minimum'])]
        
        # dates in datetime foramt
        start_date = datetime.strptime(song_start['added_at'], '%Y-%m-%dT%H:%M:%SZ')
        end_date = datetime.strptime(song_end['added_at'], '%Y-%m-%dT%H:%M:%SZ')
        min_date = datetime.strptime(song_min['added_at'], '%Y-%m-%dT%H:%M:%SZ')
        # duration in days
        delta = (end_date - start_date)
        delta_days = delta.days
        # dates formatted
        start_date_formatted = f'{start_date.day} of {start_date.strftime("%B")}, {start_date.year}'
        min_date_formatted = f'{min_date.day} of {min_date.strftime("%B")}, {min_date.year}'
        end_date_formatted = f'{end_date.day} of {end_date.strftime("%B")}, {end_date.year}'
        # duration in rows
        delta_entries = abs(int(song_end['playlist_place']) - int(song_start['playlist_place']))
        # song names
        song_start_name = '{} - {}'.format(song_start['name'], song_start['artists'])
        song_end_name = '{} - {}'.format(song_end['name'], song_end['artists'])

        song_start_uri = song_start['id']
        song_min_uri = song_min['id']
        song_end_uri = song_end['id']

        song_min_name = '{} - {}'.format(song_min['name'], song_min['artists'])

        song_start_index = int(song_start['playlist_place'])
        song_end_index = int(song_end['playlist_place'])

        # cycle depth
        doc = cycl.loc[index]['doc']
        df_new.loc[i] = [start_date_formatted, end_date_formatted, min_date_formatted, delta_days, delta_entries, doc, song_start_name, song_end_name, song_min_name, song_start_uri, song_min_uri, song_end_uri, song_start_index, song_end_index]
        i+=1 

    
    ma_series.index = ma_series.index.map(format_date)



    labels = ma_series.index.tolist()
    values = ma_series.values.tolist()


    return json.loads(df_new.to_json()), labels, values, rolling_window
        


    










