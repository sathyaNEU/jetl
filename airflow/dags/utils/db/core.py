import snowflake.connector as sf
import pandas as pd
import os
import json

def sf_client():
    conn = sf.connect(
      user=os.getenv('SF_USER'),
      password=os.getenv('SF_PASSWORD'),
      account=os.getenv('SF_ACCOUNT'),
      warehouse="BOTFOLIO_WH",
      database="BOTFOLIO_DB",
      schema="APP",
      role="BOTFOLIO"
    )
    return conn

 