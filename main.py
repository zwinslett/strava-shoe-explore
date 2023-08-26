import matplotlib.pyplot as plt
import matplotlib.ticker as plticker
import pandas as pd
import requests
import urllib3
from IPython.display import display
from pandas import json_normalize

import login as login

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

auth_url = 'https://www.strava.com/oauth/token'
activities_url = 'https://www.strava.com/api/v3/athlete/activities'

payload = {
    'client_id': f'{login.client_id}',
    'client_secret': f'{login.client_secret}',
    'refresh_token': f'{login.refresh_token}',
    'grant_type': 'refresh_token',
    'f': 'json'
}

print('Requesting Token...\n')
res = requests.post(auth_url, data=payload, verify=False)
access_token = res.json()['access_token']

header = {'Authorization': 'Bearer ' + access_token}


# The Strava API only supports 200 results per page. This function loops through each page until new_results is empty.
def loop_through_pages():
    # start at page 1
    page = 1
    # set new_results to True initially
    new_results = True
    # create an empty array to store our combined pages of data in
    data = []
    while new_results:
        # request a page + 200 results
        get_strava = requests.get(activities_url, headers=header, params={'per_page': 200, 'page': f'{page}'}).json()
        # save the response to new_results to check if its empty or not and close the loop
        new_results = get_strava
        # add our responses to the data array
        data.extend(get_strava)
        # increment the page
        page += 1
    # return the combine results of our get requests
    return data


my_dataset = loop_through_pages()
activities = json_normalize(my_dataset)


def meters_to_miles():
    activities.distance = activities.distance / 1609


def mph_convert():
    activities.average_speed = activities.average_speed * 2.237


def autopct_format(values):
    def my_format(pct):
        total = sum(values)
        val = int(round(pct * total / 100.0))
        return '{:.1f}%\n({v:d})'.format(pct, v=val)

    return my_format


meters_to_miles()
mph_convert()
df = pd.DataFrame(data=activities)
df['total_runs'] = df.groupby('id')['gear_id'].transform('count')
# Create a new dataframe grouped by gear_id. this will be useful for simplified visualizations like pie charts
# as well as making GET requests to the gear endpoint later without having to check for uniqueness
df2 = df.groupby(['gear_id']).sum().reset_index()

# Create a dictionary for storing the original gear_ids and their new names from the gear endpoint
model_lookup = dict()
# Create a list to store the gear_ids of shoes with less than 50 miles in distance
shoes_removed = []
# Loop through each gear_id in df2, make a GET request to the gear endpoint using the current gear_id,
# save the name of the gear to the dictionary
for index, row in df2.iterrows():
    original_id = row['gear_id']
    url = f'https://www.strava.com/api/v3/gear/{original_id}'
    response = requests.get(url, headers=header)
    model = response.json()
    # replaced this with the .replace() method below. will remove later once I am sure what's more efficient.
    # df2.loc[df2['gear_id'] == original_id, 'gear_id'] = model['model_name']
    model_lookup[original_id] = model['model_name']
    # Find shoes with less than 50 miles in distance and save them to a list.
    if model['converted_distance'] < 50:
        shoes_removed.append(model['model_name'])
    if model['retired']:
        shoes_removed.append(model['model_name'])

# replace the gear_ids in the two dataframes with the new values saved to the shoe_lookup dictionary
df['gear_id'] = df['gear_id'].replace(model_lookup)
df2['gear_id'] = df2['gear_id'].replace(model_lookup)

# Drop the gear_ids in the distance_look up list from df.
for index, row in df.iterrows():
    x = row['gear_id']
    y = index
    if x in shoes_removed:
        df.drop(y, axis=0, inplace=True)

# Drop the gear_ids in the distance_look up list from df2.
for index, row in df2.iterrows():
    x = row['gear_id']
    y = index
    if x in shoes_removed:
        df2.drop(y, axis=0, inplace=True)

pd.options.display.float_format = '{:,.2f}'.format
pd.set_option('display.max_columns', None)
df['avg_cadence'] = df['average_cadence'] * 2
df2['avg_pace'] = df2['moving_time'] / df2['distance']
df2.sort_values(by=['avg_pace'], inplace=True, ascending=False)
df2['avg_pace_labels'] = pd.to_datetime(df2['avg_pace'], unit='s').dt.strftime('%M:%S')
df2['moving_time'] = pd.to_datetime(df2['moving_time'], unit='s').dt.strftime('%H:%M:%S')
df2['avg_heartrate'] = df2['average_heartrate'] / df2['total_runs']
df2['avg_distance'] = df2['distance'] / df2['total_runs']
df2 = df2[['gear_id', 'moving_time', 'distance', 'avg_pace', 'total_runs', 'avg_pace_labels', 'avg_distance']]


# Make a pie chart of total runs
fig, ax = plt.subplots(figsize=(8, 8))
ax.pie(df2.total_runs, autopct=autopct_format(df2.total_runs))
ax.legend(labels=df2.gear_id, loc='best', bbox_to_anchor=(.3, .3))
ax.set_title('Percentage of Total Runs')
plt.savefig('total_runs_pie_chart.png', bbox_inches='tight', dpi=200)

# Make a pie chart of total miles
fig2, ax2 = plt.subplots(figsize=(8, 8))
ax2.pie(df2.distance, autopct=autopct_format(df2.distance))
ax2.legend(labels=df2.gear_id, loc='best', bbox_to_anchor=(.3, .3))
ax2.set_title('Percentage of Total Miles')
plt.savefig('total_distance_pie_chart.png', bbox_inches='tight', dpi=200)

# Make a scatter plot comparing shoes by avg_pace
fig3, ax3 = plt.subplots(figsize=(8, 8))
ax3.scatter(df2.avg_pace, df2.gear_id)
ax3.set_title('Average Pace by Shoe')
ax3.set_xticks(df2.avg_pace, df2.avg_pace_labels, rotation=90)
ax3.set_xlabel('Average Pace')
ax3.set_ylabel('Shoe')
ax3.invert_xaxis()
ax3.xaxis.set_minor_locator(plticker.LinearLocator())
fig3.tight_layout()
plt.savefig('avg_pace_scatter_plot.png', bbox_inches='tight', dpi=200)

# Make a box plot comparing shoes by relative effort
fig4, ax4 = plt.subplots()
ax4 = df.boxplot(by='gear_id', column=['suffer_score'], showmeans=True, meanline=True)
plt.xticks(rotation=45)
plt.minorticks_on()
ax4.yaxis.set_minor_formatter(plticker.ScalarFormatter())
ax4.get_figure().suptitle('')
ax4.set_xlabel('Shoe')
ax4.set_ylabel('Relative Effort')
ax4.set_title('Relative Effort Box Plot')
fig4.tight_layout()
plt.savefig('relative_effort_box_plot', bbox_inches='tight', dpi=200)

# Make a box plot comparing shoes by distance per activity.
fig5, ax5 = plt.subplots()
ax5 = df.boxplot(by='gear_id', column=['distance'], showmeans=True, meanline=True)
plt.xticks(rotation=45)
plt.minorticks_on()
ax5.yaxis.set_minor_formatter(plticker.ScalarFormatter())
ax5.get_figure().suptitle('')
ax5.set_xlabel('Shoe')
ax5.set_ylabel('Distance')
ax5.set_title('Distance Box Plot')
fig5.tight_layout()
plt.savefig('distance_box_plot', bbox_inches='tight', dpi=200)

# Make a boxplot comparing shoes by average cadence.
fig6, ax6 = plt.subplots()
ax6 = df.boxplot(by='gear_id', column=['avg_cadence'], showmeans=True, meanline=True)
plt.xticks(rotation=45)
plt.minorticks_on()
ax6.yaxis.set_minor_formatter(plticker.ScalarFormatter())
ax6.get_figure().suptitle('')
ax6.set_xlabel('Shoe')
ax6.set_ylabel('Cadence')
ax6.set_title('Cadence Box Plot')
fig6.tight_layout()
plt.savefig('cadence_box_plot', bbox_inches='tight', dpi=200)

# Make a box plot comparing shoes by heartrate during activity.
fig7, ax7 = plt.subplots()
ax7 = df.boxplot(by='gear_id', column=['average_heartrate'], showmeans=True, meanline=True)
plt.xticks(rotation=45)
plt.minorticks_on()
ax7.yaxis.set_minor_formatter(plticker.ScalarFormatter())
ax7.get_figure().suptitle('')
ax7.set_xlabel('Shoe')
ax7.set_ylabel('Heartrate')
ax7.set_title('Heartrate Box Plot')
fig7.tight_layout()
plt.savefig('heartrate_box_plot', bbox_inches='tight', dpi=200)

# Make a box plot comparing shoes by average speed during activity.
fig8, ax8 = plt.subplots()
ax8 = df.boxplot(by='gear_id', column=['average_speed'], showmeans=True, meanline=True)
plt.xticks(rotation=45)
plt.minorticks_on()
ax8.yaxis.set_minor_formatter(plticker.ScalarFormatter())
ax8.get_figure().suptitle('')
ax8.set_xlabel('Shoe')
ax8.set_ylabel('Speed')
ax8.set_title('Speed Box Plot')
fig8.tight_layout()
plt.savefig('speed_box_plot', bbox_inches='tight', dpi=200)
