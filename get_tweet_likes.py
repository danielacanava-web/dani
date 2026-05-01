import requests
import csv

BEARER_TOKEN = "PASTE_YOUR_BEARER_TOKEN_HERE"

tweet_urls = [
    "https://x.com/aifrontliner/status/2046974101651132851",
    "https://x.com/aiscout22/status/2047008061676720196",
    "https://x.com/anjum_ai/status/2046960190864654630",
    "https://x.com/Ben_escrito/status/2046963040244171104",
    "https://x.com/BoringBiz_/status/2047091949887226310",
    "https://x.com/DataChaz/status/2046975999913709725",
    "https://x.com/diptish09/status/2046974327875371473",
    "https://x.com/ecommartinez/status/2046963983383671056",
    "https://x.com/future_coded/status/2046961929714073606",
    "https://x.com/futurestacked/status/2046974256412516836",
    "https://x.com/GrowAIHub/status/2046957307989565511",
    "https://x.com/hey_abusiddik/status/2046977604746650100",
    "https://x.com/hey_mujeebahmed/status/2046961482425053520",
    "https://x.com/heysajib/status/2047004465627341212",
    "https://x.com/i/status/2046955801089364477",
    "https://x.com/i/status/2046956467224490133",
    "https://x.com/i/status/2046960048556175526",
    "https://x.com/i/status/2046962440278347916",
    "https://x.com/i/status/2046962641705558314",
    "https://x.com/i/status/2046964318491795754",
    "https://x.com/i/status/2046972204445991286",
    "https://x.com/i/status/2046979280677048328",
    "https://x.com/i/status/2046996835697647677",
    "https://x.com/IA_Quijote/status/2046955807124738398",
    "https://x.com/iam_chonchol/status/2046957209905742269",
    "https://x.com/iamfakhrealam/status/2046956858787954764",
    "https://x.com/Kawsar_Ai/status/2046958543614648497",
    "https://x.com/LucasMestreIA/status/2047001473763164308",
    "https://x.com/manishkumar_dev/status/2046974958472135163",
    "https://x.com/Marco_Exito/status/2047022845037817894",
    "https://x.com/MatiasSchrank/status/2047106479056880062",
    "https://x.com/Nijol71/status/2046960814574485614",
    "https://x.com/Parul_Gautam7/status/2046957954503676228",
    "https://x.com/polanco_ia/status/2047006441085575526",
    "https://x.com/pushkersoni72/status/2046956518751502632",
    "https://x.com/Rana_kamran43/status/2046967678766829856",
    "https://x.com/saidul_dev/status/2046958001563770994",
    "https://x.com/soni_jyoti_/status/2046970298248143173",
    "https://x.com/svpino/status/2046993947105649094",
    "https://x.com/techwithakansha/status/2046989031020585200",
    "https://x.com/theaicolony/status/2046973322047488366",
    "https://x.com/vermaaakash3/status/2046964045228671124",
]

def extract_tweet_id(url):
    return url.rstrip("/").split("/")[-1].split("?")[0]

def fetch_tweet_metrics(tweet_ids):
    url = "https://api.twitter.com/2/tweets"
    headers = {"Authorization": f"Bearer {BEARER_TOKEN}"}
    params = {
        "ids": ",".join(tweet_ids),
        "tweet.fields": "public_metrics,author_id",
        "expansions": "author_id",
        "user.fields": "username",
    }
    response = requests.get(url, headers=headers, params=params)
    if response.status_code != 200:
        print(f"Error {response.status_code}: {response.text}")
        return None
    return response.json()

def main():
    id_to_url = {}
    for url in tweet_urls:
        tweet_id = extract_tweet_id(url)
        id_to_url[tweet_id] = url

    tweet_ids = list(id_to_url.keys())

    # API allows max 100 IDs per request
    results = []
    for i in range(0, len(tweet_ids), 100):
        batch = tweet_ids[i:i+100]
        data = fetch_tweet_metrics(batch)
        if not data:
            continue

        # Build a map of user_id -> username
        users = {}
        if "includes" in data and "users" in data["includes"]:
            for user in data["includes"]["users"]:
                users[user["id"]] = user["username"]

        for tweet in data.get("data", []):
            metrics = tweet.get("public_metrics", {})
            username = users.get(tweet.get("author_id", ""), "unknown")
            results.append({
                "tweet_url": id_to_url.get(tweet["id"], ""),
                "username": username,
                "tweet_id": tweet["id"],
                "likes": metrics.get("like_count", 0),
                "retweets": metrics.get("retweet_count", 0),
                "replies": metrics.get("reply_count", 0),
                "views": metrics.get("impression_count", 0),
            })

    # Sort by likes descending
    results.sort(key=lambda x: x["likes"], reverse=True)

    output_file = "tweet_likes.csv"
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["tweet_url", "username", "tweet_id", "likes", "retweets", "replies", "views"])
        writer.writeheader()
        writer.writerows(results)

    print(f"Done! Saved {len(results)} tweets to {output_file}")
    print("\nTop 5 by likes:")
    for r in results[:5]:
        print(f"  @{r['username']}: {r['likes']} likes — {r['tweet_url']}")

if __name__ == "__main__":
    main()
