import pandas as pd
import warnings
import re
import os
import time
from collections import namedtuple
import selenium.webdriver as webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import ElementNotInteractableException, NoSuchElementException
from bs4 import BeautifulSoup
from string import ascii_lowercase, ascii_uppercase

warnings.filterwarnings("ignore")

user_agent = 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Mobile Safari/537.36'
path = os.path.join(os.getcwd(), 'geckodriver.exe')
service = Service(path)
option = Options()
option.set_preference('general.useragent.override', user_agent)
driver = webdriver.Firefox(service= service, options=option)

url = "https://boston.craigslist.org/search/ggg?bundleDuplicates=1&is_paid=yes#search=1~thumb~0~0"
driver.get(url)
time.sleep(3)

#Checking that the data is on the driver

#driver.save_screenshot("ss.png")
#screenshot = Image.open("ss.png")
#screenshot.show()

# Check that driver is not IP blocked

#listArea = driver.find_element(By.ID, 'search-results-page-1')
#html = driver.page_source
#print(html)
#print(listArea.location)
#print(listArea.is_enabled())

###### Grabbing Necessary Data ######
listHTML = []
stopTrack = False

print('Collecting Data')
while stopTrack == False:
    resultOL = driver.find_element(By.TAG_NAME, 'ol')
    exp =  BeautifulSoup(resultOL.get_attribute('innerHTML'), 'html.parser')
    listHTML.extend(exp.find_all('li', {'class': 'cl-search-result cl-search-view-mode-thumb'}))
    # Continue to next page
    try: 
        driver.execute_script('window.scrollTo(0,0)')
        next_button = driver.find_element(By.XPATH, '//button[@class="bd-button cl-next-page icon-only"]')
        next_button.click()
        time.sleep(1)
    
    # Stop proceding to next page at the final page
    except (ElementNotInteractableException, NoSuchElementException): 
        stopTrack = True
        pass

print('Finished Collecting Data')
driver.close()

## Formatting, Loading Data Into DataFrame

CraigslistPost = namedtuple('CraigslistPost', ['title', 'price', 'location'])
posts = []
for post in listHTML:
    title = post.find('a', 'titlestring').text
    price = post.find('div', 'meta').text
    price = re.findall('·(.*)hide', str(price))[0]
    location = post.find('div', 'supertitle').text
    posts.append(CraigslistPost(title, price, location ))

pd.set_option('display.max_columns', None)
df = pd.DataFrame(posts)

df = df.astype({"title": 'string', "price": 'string', "location": 'string'})

# Ensure that the salary column contains numbers, and that the job is paid hourly
df = df[df["price"].str.contains(pat = '.*[0-9].*', regex = True)]
dfHourOnly = df[df["price"].str.contains(pat = '.*(hr|hour|hours)+.*', regex = True)]


ascii_letters = ascii_lowercase + ascii_uppercase
# Remove Characters
for i in ascii_letters:
     dfHourOnly['price'] = dfHourOnly['price'].str.replace(str(i),'')
# Remove spaces, slashes, parentheses, '+', '$', '~', etc. 
dfHourOnly['price'] = dfHourOnly['price'].str.replace('+','')
dfHourOnly['price'] = dfHourOnly['price'].str.replace('$','')
dfHourOnly['price'] = dfHourOnly['price'].str.replace('/','')
dfHourOnly['price'] = dfHourOnly['price'].str.replace('(','')
dfHourOnly['price'] = dfHourOnly['price'].str.replace(')','')
dfHourOnly['price'] = dfHourOnly['price'].str.replace('~','')
dfHourOnly['price'] = dfHourOnly['price'].str.replace('%','')
dfHourOnly['price'] = dfHourOnly['price'].str.replace('-',' ')
dfHourOnly['price'] = dfHourOnly['price'].str.replace(':','')
dfHourOnly['price'] = dfHourOnly['price'].str.replace('!','')
dfHourOnly['price'] = dfHourOnly['price'].str.replace(',','')
dfHourOnly['price'] = dfHourOnly['price'].str.replace(' ','')
dfHourOnly['price'] = dfHourOnly['price'].str.replace('.','')

dfHourOnly = dfHourOnly.reset_index()  # make sure indices pair with number of rows
for index, row in dfHourOnly.iterrows():
    # This case occurs when there is a salary range (i.e "$20-25"). In this case we take the max 
    # possible hourly payment
    if len(row['price']) == 4:
        row['price'] = row['price'][-2:]
        dfHourOnly['price'][index] = row['price']
    # This case occurs when there is a salary range (i.e "$20.00-25.00"). In this case we take the max 
    # possible hourly payment
    if len(row['price']) == 10:
        row['price'] = row['price'][-5:]
        dfHourOnly['price'][index] = row['price']
    # This case occurs when there is a format standardization issue, or the parsing is incorrect. Since we never see
    # a 4 figure hourly salary (or more), we take the farthest two digits of these mistakes. After checking the cases in which
    # these issues occur, I found that taking the right-most two digits generally gave the correct value.
    if len(row['price']) > 3:
        row['price'] = row['price'][-2:]
        dfHourOnly['price'][index] = row['price']
    
        

    ## DECISION TO REMOVE ANYTHING THAT PAYS >$200 per hour. When looking at the data, this is very unlikely,
    ## and it is hard to standardize the formatting such that there isn't a single parsing error when changing
    ## the price column into a number type

# Make Price numeric and filter out values over $200.
dfHourOnly['price'] = pd.to_numeric(dfHourOnly['price'])
dfHourOnly = dfHourOnly[dfHourOnly['price'] < 200]
dfHourOnly = dfHourOnly.sort_values(by='price', ascending=False)
dfHourOnly = dfHourOnly.drop_duplicates(subset=["title"], keep='first')
dfHourOnly = dfHourOnly.reset_index()  # make sure indexes pair with number of rows

dfHourOnly = dfHourOnly.drop(['level_0', 'index'], axis=1)
dfHourOnly = dfHourOnly.rename(columns={"title": "title", "price": "hourly rate", "location":"location"})
# Below was used to verify formatting + debug
# print(dfHourOnly.to_string())
topPaying = dfHourOnly['hourly rate'].iloc[0]
topPayingFullDay = topPaying * 24
salary_list = dfHourOnly['hourly rate'].tolist()
salary_list_24 = [i * 24 for i in salary_list]
max_profit_daily = sum(salary_list_24)
top3Profit = 8 * (dfHourOnly['hourly rate'].iloc[0] + dfHourOnly['hourly rate'].iloc[1] + dfHourOnly['hourly rate'].iloc[2])

print('')
print('Note: The following answers are calculated with many assumptions made, and they should be regarded more as estimates than objective truth')
print('-----------------------------------------------------------------------------------------------------------------------------------------')
print('-----------------------------------------------------------------------------------------------------------------------------------------')
print('If we somehow managed to do ALL gigs in 24 hours, for 24 hours each, the maximum total Craigslist profit available on a given day is:')
print('${0}'.format(max_profit_daily))
print('-----------------------------------------------------------------------------------------------------------------------------------------')
print('-----------------------------------------------------------------------------------------------------------------------------------------')
print('The calculations below are for my interest and for different interpretations of the question.')
print('-----------------------------------------------------------------------------------------------------------------------------------------')
print('If we are to work the top paying Gig for 24 hours straight (assuming this is allowed), we would make ${0}.'.format(topPayingFullDay))
print('If we did the top 3 gigs for 8 hours each, the profit made on a given day is ${0}.'.format(top3Profit))


# Uncomment line and run the script to export the data as a csv
# dfHourOnly.to_csv('BostonGigPricesCleaned.csv', index=False)