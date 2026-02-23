import requests
import idna

# Retrieve the gTLD list from the URL
url = 'https://data.iana.org/TLD/tlds-alpha-by-domain.txt'
response = requests.get(url)
response.raise_for_status()
data = response.text

# Process the gTLD list
gtld_list = []
for line in data.splitlines():
    if not line.startswith('#'):
        decoded_line = idna.decode(line)
        gtld_list.append(decoded_line)

# Save the decoded list to a file
with open('gtlds.txt', 'w', encoding='utf-8') as file:
    for gtld in gtld_list:
        file.write(gtld + '\n')

print("Decoded gTLD list saved to gtlds.txt")
