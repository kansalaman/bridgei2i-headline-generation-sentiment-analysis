from ast import parse
import pdb
import sys
import nltk
from yaml import compose_all

sys.path.append('..')

from Task2.utils import approximate_string_match, get_context_sentences, get_pr_metrics, partition_data, read_ce_data
from Task2.company_map import company_map
import argparse
import json
from google_trans_new import google_translator
from tqdm import tqdm

translator = google_translator() 

capital_map = {
    'Bsnl' : 'BSNL',
    'Hmd' : 'HMD',
    'Zte' : 'ZTE',
    'Oneplus' : 'OnePlus',
    'Mediatek' : 'MediaTek',
    'Blackberry' : 'BlackBerry'
}

def map_capital(company):
    company = company[0].upper()+company[1:]
    if company in capital_map:
        return capital_map[company]
    else:
        return company

def get_companies(ce_data,args):
    if not args.read_companies:
        companies = []
        for datum in ce_data:
            for company,sentiment in datum['companies']:
                companies.append(company)
    else:
        with open(args.company_json_path) as company_json_file:
            companies = json.load(company_json_file)
        
    for company in companies[:61]:
        capital_map[company] = company[0].upper()+company[1:]
    
    # hindi_companies = []

    # print('translating companies...')
    # for company in tqdm(companies):
    #     hindi_company = translator.translate(company,lang_src='en',lang_tgt='hi').lower().strip()
    #     if hindi_company != company and company != 'xiamoi':
    #         company_map[hindi_company] = company
    #     hindi_companies.append(hindi_company.strip())
    
    
    if args.store_companies:
        with open(args.company_json_path,'w') as company_json_file:
            json.dump(companies,company_json_file,indent=2)

    # companies.extend(hindi_companies)
    print(companies)
    
    return set(companies)

def map_company(company):
    while company in company_map:
        # print(company)
        company = company_map[company]
    return company


def predict_companies(datum, company_list, args):
    predicted_companies = set()
    sentences = nltk.sent_tokenize(datum['raw_text'])
    datum['company_extractions'] = {}

    print(datum['doc_id'],'-------------------------------')
    # print(datum['raw_text'])
    
    for i,sentence in enumerate(sentences):
        tokens = nltk.word_tokenize(sentence)
        for j,token in enumerate(tokens):
            for company in company_list:
                if company=='-':
                    continue
                match_ratio = approximate_string_match(token.lower(),company.lower())

                if match_ratio >= args.token_match_threshold:
                    # print(token,company,match_ratio)
                    extracted_company = map_capital(map_company(company))

                    predicted_companies.add(extracted_company)
                    if extracted_company not in datum['company_extractions']:
                        datum['company_extractions'][extracted_company] = []
                    datum['company_extractions'][extracted_company].append([
                        token,
                        get_context_sentences(sentences,i,args.sentence_context_window if 'article' in datum['doc_id'] else 0)
                    ])
                    break
    
    return list(predicted_companies)
    


def ce_fuzzymatch_eval(ce_data_dev, company_list, args):
    precision_numerator = 0
    precision_denominator = 0
    recall_numerator = 0
    recall_denominator = 0

    for datum in ce_data_dev:
        predictd_companies_list = predict_companies(datum,company_list, args)
        datum_metrics = get_pr_metrics(predictd_companies_list,[
            map_capital(map_company(x[0])) for x in datum['companies']
        ])
        precision_numerator += datum_metrics[0]
        precision_denominator += datum_metrics[1]
        recall_numerator += datum_metrics[2]
        recall_denominator += datum_metrics[3]
    
    if args.eval == 'on':
    
        return {
            'precision' : precision_numerator/precision_denominator,
            'recall' : recall_numerator/recall_denominator
        }
    
    else:
        return {
            'precision' : 0,
            'recall' : 0
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='')

    parser.add_argument('--labeled_csv_file_path',required=True)
    parser.add_argument('--dev_ratio',required=True,type=float)
    parser.add_argument('--token_match_threshold', type=float)
    parser.add_argument('--store_companies', action='store_true')
    parser.add_argument('--read_companies', action='store_true')
    parser.add_argument('--company_json_path')
    parser.add_argument('--data_type',choices=['tweets','articles'])
    parser.add_argument('--sentence_context_window',type=int)
    parser.add_argument('--data_json_out_path')
    parser.add_argument('--skip_first_line',action='store_true')
    parser.add_argument('--eval', choices=['on','off'], default='on')
    
    args = parser.parse_args()

    ce_data = read_ce_data(args.labeled_csv_file_path,args)
    ce_data_train, ce_data_dev = partition_data(ce_data,args.dev_ratio)

    company_list = get_companies(ce_data_train,args)


    if args.dev_ratio > 0:
        metrics = ce_fuzzymatch_eval(ce_data_dev,company_list,args)

        print(json.dumps(
            metrics,
            indent = 2
        ))


    if args.data_json_out_path:
        with open(args.data_json_out_path,'w') as data_json_out:
            json.dump(
                ce_data_dev,
                data_json_out,
                indent=2,
                ensure_ascii=False
            )

