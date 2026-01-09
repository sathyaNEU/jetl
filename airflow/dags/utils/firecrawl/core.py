from firecrawl import FirecrawlApp

def scrape_this_site(link):
    try:
        app = FirecrawlApp()
        response = app.scrape_url(url=link, params={
            'formats': [ 'markdown' ],
        })
        return response['markdown']
    except:
        return ""