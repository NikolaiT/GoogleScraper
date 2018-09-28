FROM python:3.6

# Install chrome driver
WORKDIR /app/chromeDriver
RUN apt-get update
RUN apt-get install unzip
RUN wget https://chromedriver.storage.googleapis.com/2.42/chromedriver_linux64.zip
RUN unzip chromedriver_linux64.zip
RUN apt-get remove -y unzip

# Install gecko driver
WORKDIR /app/geckoDriver
RUN wget https://github.com/mozilla/geckodriver/releases/download/v0.22.0/geckodriver-v0.22.0-linux64.tar.gz
RUN tar -zxvf geckodriver-v0.22.0-linux64.tar.gz


WORKDIR /app/GoogleScraper
RUN pip install git+git://github.com/NikolaiT/GoogleScraper/
RUN sed -i "/chromedriver_path =/c\chromedriver_path = '/app/chromeDriver/chromedriver'" /usr/local/lib/python3.6/site-packages/GoogleScraper/scrape_config.py 
RUN sed -i "/geckodriver_path =/c\geckodriver_path = '/app/geckoDriver/geckodriver'" /usr/local/lib/python3.6/site-packages/GoogleScraper/scrape_config.py 

ENTRYPOINT bash
