from Tools import tools_v000 as tools
import crawler




import time






















# Open Browser
tools.openBrowserChrome()

start_url = ''

time.sleep(2)

result = crawler.crawl_and_save(
	driver=tools.driver,
	start_url=start_url,
	output_root='output',
	max_depth=4,
	delay_seconds=2,
)

print('Root URL     : ' + result.get('root_url', ''))
print('Total pages  : ' + str(result.get('total_pages', 0)))
print('Space key    : ' + result.get('space_key', ''))
print('Saved        : output/pages/* + output/crawl_index.json')


