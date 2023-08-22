import matplotlib.pyplot as plt
import matplotlib.ticker as plticker
import pandas as pd
import requests
import urllib3
from IPython.display import display
from pandas import json_normalize

import login as login

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

auth_url = "https://www.strava.com/oauth/token"
activities_url = "https://www.strava.com/api/v3/athlete/activities"

payload = {
    'client_id': f'{login.client_id}',
    'client_secret': f'{login.client_secret}',
    'refresh_token': f'{login.refresh_token}',
    'grant_type': "refresh_token",
    'f': 'json'
}

print("Requesting Token...\n")
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
        get_strava = requests.get(activities_url, headers=header, params={'per_page': 200, 'page': f"{page}"}).json()
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
shoe_lookup = dict()
# Loop through each gear_id in df2, make a GET request to the gear endpoint using the current gear_id,
# save the name of the gear to the dictionary
for index, row in df2.iterrows():
    original_id = row['gear_id']
    url = f"https://www.strava.com/api/v3/gear/{original_id}"
    response = requests.get(url, headers=header)
    model = response.json()
    # replaced this with the .replace() method below. will remove later once I am sure what's more efficient.
    # df2.loc[df2['gear_id'] == original_id, 'gear_id'] = model['model_name']
    shoe_lookup[original_id] = model['model_name']

# replace the gear_ids in the two dataframes with the new values saved to the shoe_lookup dictionary
df['gear_id'] = df['gear_id'].replace(shoe_lookup)
df2['gear_id'] = df2['gear_id'].replace(shoe_lookup)

pd.options.display.float_format = '{:,.2f}'.format
pd.set_option('display.max_columns', None)
df2['avg_pace'] = df2['moving_time'] / df2['distance']
df2.sort_values(by=['avg_pace'], inplace=True, ascending=False)
df2['avg_pace_labels'] = pd.to_datetime(df2['avg_pace'], unit='s').dt.strftime("%M:%S")
df2['moving_time'] = pd.to_datetime(df2['moving_time'], unit='s').dt.strftime("%H:%M:%S")
df2['avg_relative_effort'] = df2['suffer_score'] / df2['total_runs']
df2['avg_speed'] = df2['average_speed'] / df2['total_runs']
df2['avg_heartrate'] = df2['average_heartrate'] / df2['total_runs']
df2['avg_distance'] = df2['distance'] / df2['total_runs']
df2 = df2[['gear_id', 'moving_time', 'distance', 'avg_pace', 'total_runs', 'avg_relative_effort', 'avg_speed',
           'avg_heartrate', 'avg_pace_labels', 'avg_distance', 'suffer_score']]

# Make a table displaying all the data frame
fig, ax = plt.subplots()
table = ax.table(cellText=df2.values, colLabels=df2.columns, loc='center')
ax.set_position([0, 0, 1, 1])
plt.show()

# Make a scatter plot comparing shoes by average speed
fig2, ax2 = plt.subplots(figsize=(8, 8))
ax2.scatter(df2.avg_speed, df2.gear_id)
ax2.set_title("Average Speed by Shoe")
ax2.set_xlabel("MPH")
ax2.set_ylabel("Shoe")
ax2.set_yticks(df2.gear_id, df2.gear_id)
fig2.tight_layout()
plt.savefig('avg_speed_scatter_plot.png', bbox_inches='tight', dpi=200)
plt.show()

# Make a pie chart of total runs
fig3, ax3 = plt.subplots(figsize=(8,8))
ax3.pie(df2.total_runs, autopct=autopct_format(df2.total_runs))
ax3.legend(labels=df2.gear_id, loc='best', bbox_to_anchor=(.3, .3))
ax3.set_title("Percentage of Total Runs")
plt.savefig('total_runs_pie_chart.png', bbox_inches='tight', dpi=200)
plt.show()

# Make a pie chart of total miles
fig4, ax4 = plt.subplots(figsize=(8, 8))
ax4.pie(df2.distance, autopct=autopct_format(df2.distance))
ax4.legend(labels=df2.gear_id, loc='best', bbox_to_anchor=(.3, .3))
ax4.set_title("Percentage of Total Miles")
plt.savefig('total_distance_pie_chart.png', bbox_inches='tight', dpi=200)
plt.show()

# Make a bar chart comparing shoes by avg_relative_effort
fig5, ax5 = plt.subplots(figsize=(8,8))
ax5.bar(df2.gear_id, df2.avg_relative_effort)
ax5.set_title("Average Relative Effort by Shoe")
ax5.set_ylabel("Average Relative Effort")
ax5.set_xlabel("Shoe")
ax5.set_yticks((0, 20, 40, 60, 80))
ax5.set_xticks(df2.gear_id, df2.gear_id, rotation=45)
fig5.tight_layout()
plt.savefig('avg_relative_effort_bar_chart.png', bbox_inches='tight', dpi=200)
plt.show()

# Make a scatter plot comparing shoes by avg_pace
fig6, ax6 = plt.subplots(figsize=(8,8))
ax6.scatter(df2.avg_pace, df2.gear_id)
ax6.set_title("Average Pace by Shoe")
ax6.set_xticks(df2.avg_pace, df2.avg_pace_labels, rotation=90)
ax6.set_xlabel("Average Pace")
ax6.set_ylabel("Shoe")
ax6.invert_xaxis()
ax6.xaxis.set_minor_locator(plticker.LinearLocator())
fig6.tight_layout()
plt.savefig('avg_pace_scatter_plot.png', bbox_inches='tight', dpi=200)
plt.show()

# Make a bar chart comparing shoes by avg_heartrate
fig7, ax7 = plt.subplots(figsize=(8,8))
ax7.bar(df2.gear_id, df2.avg_heartrate)
ax7.set_title("Average Heartrate by Shoe")
ax7.set_ylabel("Average Heartate")
ax7.set_xlabel("Shoe")
ax7.set_xticks(df2.gear_id, df2.gear_id, rotation=45)
fig7.tight_layout()
plt.savefig('avg_heartrate_bar_chart.png', bbox_inches='tight', dpi=200)
plt.show()

# Make a scatter plot comparing shoes by avg_distance
fig8, ax8 = plt.subplots(figsize=(8,8))
ax8.scatter(df2.avg_distance, df2.gear_id)
ax8.set_title("Average Distance by Shoe")
ax8.set_xlabel("Average Distance")
ax8.set_ylabel("Shoe")
fig8.tight_layout()
plt.savefig('avg_distance_scatter_plot.png', bbox_inches='tight', dpi=200)
plt.show()

# This boxplot is using the un-grouped dataframe (df) instead of the dataframe grouped by gear (df2)
fig9, ax9 = plt.subplots()
ax9 = df.boxplot(by="gear_id", column=['suffer_score'], showmeans=True, meanline=True)
plt.xticks(rotation=45)
plt.minorticks_on()
ax9.yaxis.set_minor_formatter(plticker.ScalarFormatter())
plt.savefig('relative_effort_box_plot', bbox_inches='tight', dpi=200)
plt.show()

# This boxplot is using the un-grouped dataframe (df) instead of the dataframe grouped by gear (df2)
fig10, ax10 = plt.subplots()
ax10 = df.boxplot(by="gear_id", column=['distance'], showmeans=True, meanline=True)
plt.xticks(rotation=45)
plt.minorticks_on()
ax10.yaxis.set_minor_formatter(plticker.ScalarFormatter())
plt.savefig('distance_box_plot', bbox_inches='tight', dpi=200)
plt.show()

display(df2)
