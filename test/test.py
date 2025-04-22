from googletrans import Translator

def translate(query):
    try:
        translator = Translator()
        translation = translator.translate(query, src='auto', dest='en')
        return translation.text
    except Exception as e:
        print(f"翻译出错：{e}")
        return None

if __name__ == '__main__':
    query = "请在huggingface上查找数据来计算Deepseek的影响力，这个影响力可以几个数据（如收藏数，关注数，下载数等）的加权计算"
    translated_text = translate(query)
    if translated_text:
        print(translated_text)
    else:
        print("翻译失败")