import sys
import os
import ast
import json
import pandas
import sqlalchemy
import psycopg2
import streamlit 
from elasticsearch import Elasticsearch
from streamlit_js_eval import streamlit_js_eval


streamlit.set_page_config(layout = 'wide')
window_width = streamlit_js_eval(js_expressions = 'window.parent.innerWidth', key = 'BROWSER_WIDTH', want_output = True)

path = os.path.dirname(sys.argv[0])

with open(f'{path}\\password.json', 'r', encoding = 'utf-8') as file:
    password = json.load(file)

es = Elasticsearch('https://localhost:9200', verify_certs = False, basic_auth = (password['elastic']['login'], password['elastic']['password']),  headers = {"Accept": "application/vnd.elasticsearch+json; compatible-with=8"})
es.info()

engine = sqlalchemy.create_engine(f"postgresql://{password['postgresql']['login']}:{password['postgresql']['password']}@localhost:5432/{password['postgresql']['database']}")

with streamlit.container(horizontal = True):
    text_box = streamlit.text_input('qwe', label_visibility = 'collapsed')
    search = streamlit.button('Поиск')
    delete = streamlit.button('Удалить из базы')

if es.count()['count'] == 0:
    
    sql = f'select * from {password['postgresql']['table']}'
    df = pandas.read_sql(sql, engine)
    
    for _, row in df.iterrows():
        doc = row.to_dict()
        es.index(index = 'id', id = doc['id'], document = doc)

if search:
    
    query = {'match':{'text':{'query':text_box, 'fuzziness':'AUTO'}}}
    result_search = es.search(index = 'id', query = query, sort = [{'created_date': {'order': 'desc'}}], size = 20)
    ind = tuple(map(lambda x: x['_source']['id'], result_search['hits']['hits']))
    
    match len(ind):
        case 0:
            streamlit.error(f'Записей по вашему запросу не найдено')
        case 1:
            sql = f'select * from {password['postgresql']['table']} where id = {ind[0]}'
            df = pandas.read_sql(sql, engine)
            df = df.sort_values(by = 'created_date', ascending = False)
            streamlit.dataframe(df, hide_index = True)
        case _:
            sql = f'select * from {password['postgresql']['table']} where id in {ind}'
            df = pandas.read_sql(sql, engine)
            df = df.sort_values(by = 'created_date', ascending = False)
            streamlit.dataframe(df, hide_index = True)

if delete:
    
    sql = 'select exists(select 1 from ' + password['postgresql']['table'] + ' where id = ' + text_box + ')'
    
    with psycopg2.connect(dbname = 'test', user = password['postgresql']['login'], password = password['postgresql']['password'], host = 'localhost', port = '5432') as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql)
            ans = cursor.fetchall()[0][0]
    
    if ans:
        
        sql = 'delete from ' + password['postgresql']['table'] + ' where id = ' + text_box
        with psycopg2.connect(dbname = 'test', user = password['postgresql']['login'], password = password['postgresql']['password'], host = 'localhost', port = '5432') as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql)
        
        es.delete(index = 'id', id = int(text_box))
        
        streamlit.success(f'Запись {text_box} удалена из базы')
    
    else:
        streamlit.error(f'Запись {text_box} не найдена в базе данных')