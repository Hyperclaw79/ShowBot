import requests
from bs4 import BeautifulSoup as BS
import json
from datetime import datetime, timedelta
from random import choices
from flask import *

app = Flask(__name__)

dt = datetime.today()
dates = [(dt+timedelta(days=i)).strftime('%Y%m%d') for i in range(0, 4)]
display_dates = [
    'Today',
    'Tomorrow',
    (dt+timedelta(days=2)).strftime('%b %d'),
    (dt+timedelta(days=3)).strftime('%b %d')
]

city_list = [
    'Mumbai', 'Bengaluru',
    'Chennai', 'Hyderabad',
    'Kolkata', 'Pune'
]
city_codes = [
    'MUMBAI', 'BANG',
    'CHEN', 'HYD',
    'KOLK', 'PUNE'
    ]

sess = requests.Session()


def souper(url):
    response = sess.get(url)
    sauce = response.content
    return BS(sauce, 'lxml')


def generate_choices(iterable):
    s = ''
    for i, val in enumerate(iterable):
            s = s + "{}. {}\n".format(i+1, val)
    return s


def get_list(url):
    soup = souper(url)
    queries = soup.find_all('a', class_='__movie-name')
    query_list = []
    for ind in queries:
        query_list.append({ind["title"]: ind["href"].split("/")[-1]})
    return query_list


def generate_output(url):
    splitted = url.split('/buytickets/')
    base_url = splitted[0]
    command = 'GETSHOWTIMESBYEVENTANDVENUE&f=json'
    seats_url = base_url+'/serv/getData?cmd='+command
    seats_url = seats_url + '&dc={}&vc={}&ec={}'
    nextsplit = splitted[1].split('/')
    date = nextsplit[2]
    movie_code = nextsplit[1].split('-')[2]
    seats_url = seats_url.format(date,"venue_code",movie_code)
    soup = souper(url)
    theatres = soup.find_all('li', class_='list ')
    theatre_list = []
    for theatre in theatres:
        theatre_dict = {}
        venue = theatre['data-name']
        venue_code = theatre['data-id']
        raw = sess.get(seats_url.replace('venue_code',venue_code)).json()
        rel = [[{desc["PriceDesc"]:desc["SeatsAvail"]} for desc in show["Categories"]] for show in raw["BookMyShow"]["arrShows"]]
        shows = []
        for i,time in enumerate(theatre.find('div', class_='body ').find_all('div')):
            categories = json.loads(time.find('a')['data-cat-popup'])
            catog = {}
            for category in categories:
                price = category["price"]
                desc = category["desc"]
                avail = [element for element in rel[i] if list(element.keys())[0]==desc][0][desc]
                category = {"Price: ": price, "Seats: ": avail}
                catog[desc] = category
            shows.append({
                'time': time.find('a')['data-display-showtime'],
                'categories': catog
            })
        theatre_dict = {'Venue': venue, 'Shows': shows}
        theatre_list.append(theatre_dict)
    return theatre_list


@app.route('/connect', methods=['GET'])
def connect():
    """
    User wants to connect to the app.
    """
    try:
        if request.args.get('token'):
            token = request.args.get('token')
            digits = [str(i) for i in range(10)]
            letters = [chr(i) for i in range(65, 91)]
            seed = choices(letters, k=10)
            lut = dict(zip(digits, seed))
            hashed = ''.join(set([lut[c] for c in token]))
            sess.headers = {"User-Agent": "BMS-API -s {}".format(hashed)}
            return jsonify({
                "cities": generate_choices(city_list),
                "dates": generate_choices(display_dates)
            })
        else:
            return 'Please provide an access token.'
    except Exception as e:
        return 'Error: {}'.format(str(e))        

@app.route('/city', methods=['GET'])
def set_city():
    if request.args.get('reply'):
        try:
            choice = request.args.get('reply')
            city = city_list[int(choice) - 1]
            url = 'https://in.bookmyshow.com/{}/movies'.format(city)
            movie_list = get_list(url)
            return generate_choices([list(movie.keys())[0] for movie in movie_list])
        except Exception as e:
            return "Error: {}".format(str(e))
    else:
        return "No value choosen."


@app.route('/movie', methods=['GET'])
def set_movie():
    argsList = [
        'city',
        'date',
        'choice'
    ]
    reqList = list(map(request.args.get, argsList))
    if all(reqList):
        try:
            ci, date, choice = reqList
            city = city_list[int(ci)-1]
            date = dates[int(date) - 1]
            base_url = 'https://in.bookmyshow.com/{}'.format(city)
            movie_url = '{}/movies'.format(base_url)
            movie_list = get_list(movie_url)
            movie = list(movie_list[int(choice) - 1].keys())[0]
            movie = movie.replace(' ','-').replace('(','').replace(')','')
            movie_code = list(movie_list[int(choice) - 1].values())[0]
            city_code = city_codes[int(ci)-1]
            url = base_url.replace(city, 'buytickets')
            url = url + '/{}-{}/movie-{}-{}-MT/{}'.format(
                movie, city, city_code,
                movie_code, date
            )
            jsony = generate_output(url)
            return jsonify(jsony)
        except Exception as e:
            return "Error: {}".format(str(e))
    else:
        return "The following paramters were not given:" + '\n'.join(argsList)

if __name__ == '__main__':
    app.run()
