FROM apache/airflow:2.10.4

USER root

# Install wget and required dependencies
RUN apt-get update && apt-get install -y wget gnupg unzip xvfb && rm -rf /var/lib/apt/lists/*

# Add the Google Chrome repository and install Chrome
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | \
    gpg --dearmor | tee /usr/share/keyrings/google-chrome.gpg > /dev/null && \
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > \
    /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && apt-get install -y google-chrome-stable && \
    rm -rf /var/lib/apt/lists/*

# Install matching Chromedriver version (143.x to match Chrome 143.x)
ENV CHROMEDRIVER_VERSION=143.0.7499.146
ENV CHROMEDRIVER_DIR=/usr/local/bin

RUN wget -q -P /tmp "https://storage.googleapis.com/chrome-for-testing-public/${CHROMEDRIVER_VERSION}/linux64/chromedriver-linux64.zip" && \
    unzip /tmp/chromedriver-linux64.zip -d /tmp && \
    mv /tmp/chromedriver-linux64/chromedriver ${CHROMEDRIVER_DIR}/chromedriver && \
    chmod +x ${CHROMEDRIVER_DIR}/chromedriver && \
    rm -rf /tmp/chromedriver-linux64.zip /tmp/chromedriver-linux64


USER airflow
RUN pip install spacy && python -m spacy download en_core_web_sm