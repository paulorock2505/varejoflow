import os
import csv
import time
import random
import datetime
import urllib.parse
import logging
import re

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36"
]

AFFILIATE_TAG = "techrider02-20"

def add_affiliate_tag(url, tag=AFFILIATE_TAG):
    parsed = urllib.parse.urlparse(url)
    query_dict = urllib.parse.parse_qs(parsed.query)
    query_dict["tag"] = [tag]
    new_query = urllib.parse.urlencode(query_dict, doseq=True)
    new_parsed = parsed._replace(query=new_query)
    return urllib.parse.urlunparse(new_parsed)

def fetch_dynamic_page(url, timeout=60):
    logging.info(f"Acessando: {url}")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = None
        try:
            context = browser.new_context(user_agent=random.choice(USER_AGENTS))
            page = context.new_page()
            page.goto(url, timeout=timeout * 1000)
            page.wait_for_timeout(2000)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(2000)
            content = page.content()
        finally:
            if context:
                context.close()
            browser.close()
        return content


def format_price(price_whole, price_fraction):
    whole = price_whole.replace(".", "").replace(",", "")
    fraction = price_fraction.replace(",", "").replace(".", "") if price_fraction else "00"
    formatted = f"{whole}.{fraction}"
    if formatted[-1] == "0":
        formatted = formatted[:-1] + "1"
    return formatted

class AmazonDynamicScraper:
    def __init__(self, query, affiliate_tag=None, nome_lista=""):
        self.query = query
        self.affiliate_tag = affiliate_tag if affiliate_tag else AFFILIATE_TAG
        self.nome_lista = nome_lista  # Valor recebido da página amazon_search.html
        self.base_url = "https://www.amazon.com.br"
        self.products = []

    def search_products(self):
        query_formatted = self.query.replace(" ", "+")
        search_url = f"{self.base_url}/s?k={query_formatted}"
        html = fetch_dynamic_page(search_url)
        if html:
            self.parse_search_results(html)
        else:
            logging.error("Falha ao obter os resultados de busca.")

    def parse_search_results(self, html):
        soup = BeautifulSoup(html, "html.parser")
        results = soup.find_all("div", {"data-component-type": "s-search-result"})
        if not results:
            logging.warning("Nenhum produto encontrado na busca.")
            return
        terms = self.query.lower().split()
        for item in results:
            try:
                title_elem = item.find("h2")
                title = title_elem.get_text(strip=True) if title_elem else ""
                if not all(term in title.lower() for term in terms):
                    continue
                link_elem = title_elem.find("a", href=True) if title_elem else None
                if not link_elem:
                    link_elem = item.find("a", href=True)
                link = ""
                if link_elem and link_elem.get("href"):
                    link_value = link_elem.get("href")
                    if not link_value.startswith("http"):
                        link_value = self.base_url + link_value
                    link = add_affiliate_tag(link_value, tag=self.affiliate_tag)
                if not link:
                    logging.warning(f"Link não encontrado para: {title}")
                    continue
                price = ""
                price_whole_elem = item.find("span", class_="a-price-whole")
                if price_whole_elem:
                    price_fraction_elem = item.find("span", class_="a-price-fraction")
                    price = format_price(
                        price_whole_elem.get_text(strip=True),
                        price_fraction_elem.get_text(strip=True) if price_fraction_elem else "00"
                    )
                else:
                    price_offscreen = item.find("span", class_="a-offscreen")
                    if price_offscreen:
                        price = price_offscreen.get_text(strip=True).replace("R$", "").strip()
                if not price:
                    continue
                image_elem = item.find("img", class_="s-image")
                image = image_elem["src"] if image_elem and image_elem.get("src") else ""
                # Adiciona a informação de Nome da Lista a cada produto
                # Dentro do método parse_search_results de AmazonDynamicScraper
                self.products.append({
                    "Title": title,
                    "Nome da Lista": self.nome_lista,  # valor passado pelo template
                    "Marca do Produto": "",
                    "Moeda": "À VISTA R$",
                    "Preço": price,
                    "Imagem": image,
                    "Link do produto": link,
                    "Detalhes Técnicos": "",
                    "Informações Adicionais": "",
                    "Sobre este Item": ""
                })
            except Exception as e:
                logging.error(f"Erro ao processar um produto: {e}")

    def update_product_details(self):
        for product in self.products:
            if product["Link do produto"]:
                html = fetch_dynamic_page(product["Link do produto"])
                if html:
                    details = self.parse_product_page(html)
                    product.update(details)
                else:
                    logging.error(f"Falha ao obter detalhes para: {product['Link do produto']}")
                time.sleep(random.uniform(2, 4))

    def parse_product_page(self, html):
        details = {
            "Marca do Produto": "",
            "Detalhes Técnicos": "",
            "Informações Adicionais": "",
            "Sobre este Item": ""
        }
        try:
            soup = BeautifulSoup(html, "html.parser")
            brand_elem = soup.find("a", {"id": "bylineInfo"})
            if brand_elem:
                details["Marca do Produto"] = brand_elem.get_text(strip=True)
            else:
                detail_div = soup.find("div", {"id": "detailBullets_feature_div"})
                if detail_div:
                    li_items = detail_div.find_all("li")
                    for li in li_items:
                        if "Marca" in li.get_text():
                            text = li.get_text(separator=" ", strip=True)
                            parts = text.split(":", 1)
                            if len(parts) > 1:
                                details["Marca do Produto"] = parts[1].strip()
                            break
            if details["Marca do Produto"]:
                cleaned = re.sub(r"(?i)visite a loja", "", details["Marca do Produto"])
                cleaned = re.sub(r"(?i)marca:\s*", "", cleaned)
                details["Marca do Produto"] = cleaned.strip()
            tech_text = ""
            tech_table = soup.find("table", {"id": "productDetails_techSpec_section_1"})
            if tech_table:
                tech_details = tech_table.get_text(separator="\n", strip=True).split("\n")
                tech_text = "\n".join("• " + item.strip() for item in tech_details if item.strip())
            else:
                tech_table = soup.find("table", {"id": "productDetails_detailBullets_sections1"})
                if tech_table:
                    tech_details = tech_table.get_text(separator="\n", strip=True).split("\n")
                    tech_text = "\n".join("• " + item.strip() for item in tech_details if item.strip())
                else:
                    dt_div = soup.find("div", {"id": "detailBullets_feature_div"})
                    if dt_div:
                        dt_items = dt_div.get_text(separator="\n", strip=True).split("\n")
                        tech_text = "\n".join("• " + item.strip() for item in dt_items if item.strip())
            details["Detalhes Técnicos"] = tech_text
            info_text = ""
            add_info = soup.find("div", {"id": "feature-bullets"})
            if not add_info:
                add_info = soup.find("ul", {"class": "a-unordered-list a-vertical a-spacing-mini"})
            if add_info:
                info_items = add_info.get_text(separator="\n", strip=True).split("\n")
                info_text = "\n".join("• " + item.strip() for item in info_items if item.strip())
            details["Informações Adicionais"] = info_text
            desc_text = ""
            description = soup.find("div", {"id": "productDescription"})
            if not description:
                description = soup.find("div", {"id": "aboutThisItem_feature_div"})
            if description:
                desc_items = description.get_text(separator="\n", strip=True).split("\n")
                desc_text = "\n".join("• " + item.strip() for item in desc_items if item.strip())
            details["Sobre este Item"] = desc_text
        except Exception as e:
            logging.error(f"Erro ao extrair os detalhes do produto: {e}")
        return details

    def save_to_csv(self, filename):
        fieldnames = [
            "Title", "Nome da Lista", "Marca do Produto", "Moeda", "Preço",
            "Imagem", "Link do produto", "Detalhes Técnicos",
            "Informações Adicionais", "Sobre este Item"
        ]
        with open(filename, "w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.products)
        logging.info(f"Arquivo CSV '{filename}' criado com sucesso.")

def amazon_scrap_selenium(query, affiliate_tag="", nome_lista=""):
    # Essa função deve retornar uma lista de dicionários
    # onde cada produto terá o campo "Nome da Lista" adicionado
    scraper = AmazonDynamicScraper(query, affiliate_tag, nome_lista)
    scraper.search_products()
    scraper.update_product_details()
    products = scraper.products
    return products


if __name__ == "__main__":
    q = "notebook dell"
    lista = "Minha Lista Exemplo"
    prods = amazon_scrap_selenium(q, nome_lista=lista)
    for p in prods:
        print(p)
