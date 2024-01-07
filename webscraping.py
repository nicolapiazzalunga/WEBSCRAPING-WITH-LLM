from bs4 import BeautifulSoup
import requests
import openai
import os
import json
import csv
import tiktoken
import time

# LLM set up
openai.api_key = ""
def get_completion(prompt, model="gpt-3.5-turbo"):
    messages = [{"role": "user", "content": prompt}]
    response = openai.ChatCompletion.create(
        model=model,
        messages=messages,
        temperature=0, # this is the degree of randomness of the model's output
    )
    return response.choices[0].message["content"]

# Preprocessing function
def preprocess_html(text):

    # Remove uninformative text
    text = text.replace('class=" ', '')
    text = text.replace('div class=', '')
    text = text.replace('elementor', '')
    text = text.replace('element', '')
    text = text.replace('li class="', '')
    text = text.replace('/li', '')
    text = text.replace('/ul', '')
    text = text.replace('</div>', '')
    text = text.replace('</span>', '')
    text = text.replace('<', '')
    text = text.replace('>', '')
    # Break into lines and remove leading and trailing space on each
    lines = (line.strip() for line in text.splitlines())
    # Break multi-headlines into a line each
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    # Drop blank lines
    text = '\n'.join(chunk for chunk in chunks if chunk)
    return text

def save_to_csv(json_obj, filename):
    """
    Saves a JSON object to a CSV file.
    :param json_obj: The JSON object to save.
    :param filename: The name of the CSV file.
    """
    # Check if file exists
    file_exists = os.path.isfile(filename)
    try:
        with open(filename, 'a', newline='') as file:
            writer = csv.writer(file)
            if not file_exists:
                writer.writerow(json_obj.keys())
            writer.writerow(json_obj.values())
    except FileNotFoundError:
        print("The directory does not exist.")
    except PermissionError:
        print("You do not have permission to write to this file.")
    except IsADirectoryError:
        print("You are trying to write to a directory, not a file.")
    except UnicodeEncodeError:
        print("One of your data entries cannot be encoded in utf-8.")

# Set up tokenizer
encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")

# access to WEBPAGE
url = ''
response = requests.get(url)
_text = response.text

# Start from beginning
token_count = 0
request_count = 0
company_id = 0
product_id = 0

while True:

    # If list continues
    if "" in _text:
        # Get company_snippet
        start = ""
        end = ""
        start_index = _text.find(start)
        end_index = _text.find(end)
        company_snippet = preprocess_html(_text[start_index + len(start):end_index])

        # Set up for next cycle
        _text = _text[end_index+len(end):]

        # LLM it into a JSON
        prompt = f"""
        I am going to give you a HTML snippet containing information about a company.

        I want you to extract the company info.

        I want you to format your answer as a JSON object consistent with the following scheme:
        
        "companyID": "",
        "companyName": "",
        "country": "",
        "category": "",
        "exibitor_website": ""

        companyID is given "companyID": "{company_id}"

        -----
        The snippet: '''{company_snippet}'''
        """
        while True:
            try:
                response_json = get_completion(prompt)
            except openai.error.RateLimitError:
                print("Rate limit hit, sleeping for a minute...")
                time.sleep(60)
            break
        company_dict1 = json.loads(response_json)

        # Check for request limits
        token_count += len(encoding.encode(prompt))
        token_count += len(encoding.encode(str(company_dict1)))
        request_count += 1
        if token_count > 50000 or request_count > 3400:
            time.sleep(60)
            token_count = 0
            request_count = 0

        # Go to company profile
        try:
            url = company_dict1['exibitor_website']
            response = requests.get(url)
            _text_profile = response.text
            
            # Go to company snippet
            start = ''
            end = ''
            start_index = _text_profile.find(start)
            _text_profile = _text_profile[start_index:]
            start_index = 0
            end_index = _text_profile.find(end)
            company_snippet = preprocess_html(_text_profile[start_index:end_index])
            prompt = f"""
            I am going to give you a HTML snippet containing information about a company.

            I want you to extract the company info.

            I want you to format your answer as a JSON object consistent with the following scheme:
            
            "companyName": "",
            "stand": "",
            "about": [],
            "website": ""

            -----
            The snippet: '''{company_snippet}'''
            """
            while True:
                try:
                    response_json = get_completion(prompt)
                except openai.error.RateLimitError:
                    print("Rate limit hit, sleeping for a minute...")
                    time.sleep(60)
                break
            company_dict2 = json.loads(response_json)

            # Check for request limits
            token_count += len(encoding.encode(prompt))
            token_count += len(encoding.encode(str(company_dict2)))
            request_count += 1
            if token_count > 50000 or request_count > 3400:
                time.sleep(60)
                token_count = 0
                request_count = 0

            # Merge the company JSONs
            company_dict1.update(company_dict2)
            save_to_csv(company_dict1, 'companies.csv')

            # Get products snippets
            _text_products = _text_profile[end_index+len(end):]
            while True:
                if "<article" in _text_products:
                    # Get product_snippet
                    start = "<article"
                    end = "</article>"
                    start_index = _text_products.find(start)
                    _text_products = _text_products[start_index:]
                    start_index = 0
                    end_index = _text_products.find(end)
                    product_snippet = preprocess_html(_text_products[start_index + len(start):end_index])

                    # LLM the snippet
                    prompt = f"""
                    I am going to give you a HTML snippet containing information about a product.

                    I want you to extract the product info.

                    I want you to format your answer as a JSON object consistent with the following scheme:
                    
                    "productID": "",
                    "companyID": "",
                    "productDescription": "",
                    "productImage": "",
                    "productLink": ""

                    productID is given "productID": "{product_id}"
                    companyID is given "companyID": "{company_id}"

                    -----
                    The snippet: '''{product_snippet}'''
                    """
                    while True:
                        try:
                            response_json = get_completion(prompt)
                        except openai.error.RateLimitError:
                            print("Rate limit hit, sleeping for a minute...")
                            time.sleep(60)
                        break
                    product_dict = json.loads(response_json)

                    # Check for request limits
                    token_count += len(encoding.encode(prompt))
                    token_count += len(encoding.encode(str(product_dict)))
                    request_count += 1
                    if token_count > 50000 or request_count > 3400:
                        time.sleep(60)
                        token_count = 0
                        request_count = 0

                    # Save product to csv
                    save_to_csv(product_dict, 'products.csv')

                    # Set up for next cycle
                    _text_products = _text_products[end_index+len(end):]
                    product_id += 1
                else:
                    break
        except KeyError:
            print("KeyError")
            
        company_id += 1
    else:
        break
