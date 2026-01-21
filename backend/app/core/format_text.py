import re

def reduce_newlines_to_two(text):
  cleaned_text = re.sub(r'[\r\n]+', '\n\n', text)
  return cleaned_text
