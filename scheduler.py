import schedule
import time
from generate_xmls import GenerateXML, ElasticSearchClient
from src.config import ES_CLOUD_ID, ES_USERNAME, ES_PASSWORD, ES_INDEX


def generate_xml(url):
    gen = GenerateXML()
    # scrap data and save json and then pass it to xml
    elastic_search = ElasticSearchClient(es_cloud_id=ES_CLOUD_ID, es_username=ES_USERNAME,
                                         es_password=ES_PASSWORD)
    data_list = elastic_search.extract_data_from_es(ES_INDEX, url)
    gen.start(data_list, url)


schedule.every().day.at("23:00").do(generate_xml(url="https://lists.linuxfoundation.org/pipermail/bitcoin-dev/"))
schedule.every().day.at("02:00").do(generate_xml(url="https://lists.linuxfoundation.org/pipermail/lightning-dev/"))


while True:
    schedule.run_pending()
    time.sleep(1)
