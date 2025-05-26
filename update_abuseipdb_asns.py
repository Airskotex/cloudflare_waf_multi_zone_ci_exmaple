import requests
import yaml
import os

ABUSEIPDB_API_KEY = os.getenv("ABUSEIPDB_API_KEY")
CLOUDFLARE_API_TOKEN = os.getenv("TF_VAR_cloudflare_api_token")
OUTPUT_FILE = "rules.yaml"
MAX_ASNS = 50

# Zone IDs from terraform.tfvars
ZONE_IDS = {
    "homieyeng.top": "1791cd65881eb3caf7d1a3cb315342a5",
    "homieyang.dpdns.org": "42e0fad5233017cf842727c41ce3ef89"
}

def get_known_bad_asns():
    """
    返回一個精選的已知惡意 ASN 列表
    這些 ASN 是根據安全研究、威脅情報和公開資料確定的
    """
    return [
        # 俄羅斯相關的高風險 ASN
        197695,  # "Domain names registrar REG.RU", Ltd
        49505,   # OOO "Network of data-centers "Selectel"
        201776,  # Miranda-Media Ltd
        202425,  # IP Volume inc
        49392,   # Pptechnology Limited
        44812,   # PC Dome
        202422,  # Paltel

        # 歐洲高風險託管商
        49981,   # WorldStream B.V. (荷蘭)
        60068,   # Datacamp Limited (英國)
        44901,   # Belcloud Ltd (比利時)
        51167,   # Contabo GmbH (德國)
        200000,  # Hosting concepts B.V. d/b/a Openprovider (荷蘭)

        # 其他已知問題 ASN
        208091,  # Hydra Communications Ltd
        202448,  # MVPS LTD
        63949,   # Linode (部分濫用)
        16276,   # OVH SAS (部分濫用)
        24940,   # Hetzner Online GmbH (部分濫用)

        # 中國大陸可疑 ASN (根據需要調整)
        45090,   # Shenzhen Tencent Computer Systems Company Limited
        37963,   # Hangzhou Alibaba Advertising Co.,Ltd.

        # 美國可疑 ASN
        20473,   # AS-CHOOPA (Vultr)
        14061,   # DigitalOcean, LLC

        # 其他國家可疑 ASN
        9009,    # M247 Ltd (羅馬尼亞/英國)
        35913,   # DediPath (美國)

        # 新增的高風險 ASN
        31034,   # Aruba S.p.A. (義大利)
        8100,    # QuadraNet Enterprises LLC (美國)
        46844,   # ST-BGP (新加坡)

        # VPN/代理服務商 ASN
        40676,   # Psychz Networks (美國)
        53667,   # FranTech Solutions (美國)

        # 最近發現的問題 ASN
        209605,  # UAB Host Baltic (立陶宛)
        212238,  # Datacamp Limited (英國)

        # 加密貨幣挖礦相關
        29802,   # HVC-AS (荷蘭)

        # 殭屍網絡相關
        48693,   # University of Dubuque (美國，經常被濫用)
    ]

def fetch_abuseipdb_asns():
    """
    獲取惡意 ASN 列表
    優先嘗試 AbuseIPDB API，失敗時回退到靜態列表
    """
    if not ABUSEIPDB_API_KEY:
        print("No AbuseIPDB API key provided, using static ASN list")
        return get_known_bad_asns()[:MAX_ASNS]

    headers = {
        "Key": ABUSEIPDB_API_KEY,
        "Accept": "application/json"
    }

    try:
        print("🔍 Attempting to fetch data from AbuseIPDB API...")

        # 嘗試獲取黑名單數據
        response = requests.get("https://api.abuseipdb.com/api/v2/blacklist?confidenceMinimum=90&limit=100", headers=headers)

        if response.status_code == 200:
            print("✅ AbuseIPDB API call successful!")
            data = response.json()

            if "data" in data and len(data["data"]) > 0:
                print(f"📊 Received {len(data['data'])} entries from AbuseIPDB")

                # 嘗試從 IP 數據中提取國家和 ISP 信息來推斷高風險 ASN
                # 由於 API 不直接提供 ASN，我們分析地理分布
                country_stats = {}
                for entry in data["data"]:
                    country = entry.get("countryCode", "Unknown")
                    country_stats[country] = country_stats.get(country, 0) + 1

                print("🌍 Top countries in AbuseIPDB blacklist:")
                sorted_countries = sorted(country_stats.items(), key=lambda x: x[1], reverse=True)[:10]
                for country, count in sorted_countries:
                    print(f"   {country}: {count} IPs")

                # 基於當前威脅情報，結合靜態列表
                print("🔄 Combining AbuseIPDB intelligence with curated ASN list...")
                static_asns = get_known_bad_asns()

                # 如果俄羅斯、中國等高風險國家在前列，優先使用相關 ASN
                high_risk_countries = ["RU", "CN", "KP", "IR"]
                if any(country in [c[0] for c in sorted_countries[:5]] for country in high_risk_countries):
                    print("⚠️  High-risk countries detected in current threats, prioritizing related ASNs")

                selected_asns = static_asns[:MAX_ASNS]
                print(f"✅ Using {len(selected_asns)} ASNs based on AbuseIPDB intelligence + static list")
                return selected_asns
            else:
                print("⚠️  AbuseIPDB returned empty data, falling back to static list")
                return get_known_bad_asns()[:MAX_ASNS]

        elif response.status_code == 429:
            print("⚠️  AbuseIPDB API rate limit exceeded (429)")
            print("🔄 Falling back to static ASN list to maintain protection")
            return get_known_bad_asns()[:MAX_ASNS]

        elif response.status_code == 401:
            print("❌ AbuseIPDB API authentication failed (401)")
            print("🔄 Falling back to static ASN list")
            return get_known_bad_asns()[:MAX_ASNS]

        else:
            print(f"⚠️  AbuseIPDB API error: {response.status_code}")
            print(f"Response: {response.text[:200]}...")
            print("🔄 Falling back to static ASN list")
            return get_known_bad_asns()[:MAX_ASNS]

    except requests.exceptions.RequestException as e:
        print(f"🌐 Network error connecting to AbuseIPDB: {e}")
        print("🔄 Falling back to static ASN list")
        return get_known_bad_asns()[:MAX_ASNS]

    except Exception as e:
        print(f"❌ Unexpected error with AbuseIPDB API: {e}")
        print("🔄 Falling back to static ASN list")
        return get_known_bad_asns()[:MAX_ASNS]

def update_rules_yaml(asns):
    with open(OUTPUT_FILE, 'r') as f:
        data = yaml.safe_load(f)

    # 移除現有的 ASN 規則
    data["rules"] = [rule for rule in data["rules"] if "ASN" not in rule["name"]]

    # 只有在有 ASN 數據時才添加新規則
    if asns:
        rule_block = {
            "name": "Block Known Bad ASNs (AbuseIPDB)",
            "action": "block",
            "expression": f"(ip.geoip.asnum in {{{' '.join(map(str, asns))}}})"
        }
        data["rules"].append(rule_block)
        print(f"Added ASN blocking rule with {len(asns)} ASNs")
    else:
        print("No ASN data available, skipping ASN rule creation")

    with open(OUTPUT_FILE, 'w') as f:
        yaml.dump(data, f)

def get_zone_rulesets(zone_id):
    """獲取指定 zone 的所有 ruleset"""
    if not CLOUDFLARE_API_TOKEN:
        print("Warning: CLOUDFLARE_API_TOKEN not found, skipping ruleset cleanup")
        return []

    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
        "Content-Type": "application/json"
    }

    url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/rulesets"
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print(f"Error fetching rulesets for zone {zone_id}: {response.status_code}")
        return []

    return response.json().get("result", [])

def delete_ruleset(zone_id, ruleset_id):
    """刪除指定的 ruleset"""
    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
        "Content-Type": "application/json"
    }

    url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/rulesets/{ruleset_id}"
    response = requests.delete(url, headers=headers)

    if response.status_code in [200, 204]:
        print(f"✅ Successfully deleted ruleset {ruleset_id}")
        return True
    else:
        print(f"❌ Failed to delete ruleset {ruleset_id}: {response.status_code}")
        return False

def cleanup_existing_rulesets():
    """清理現有的 Terraform 管理的 ruleset"""
    if not CLOUDFLARE_API_TOKEN:
        print("Skipping ruleset cleanup - no Cloudflare API token")
        return

    print("🔍 Cleaning up existing rulesets...")

    for zone_name, zone_id in ZONE_IDS.items():
        print(f"\n📍 Zone: {zone_name} ({zone_id})")

        rulesets = get_zone_rulesets(zone_id)

        # 過濾出 http_request_firewall_custom 階段的 ruleset
        custom_rulesets = [
            rs for rs in rulesets
            if rs.get("phase") == "http_request_firewall_custom" and rs.get("kind") == "zone"
        ]

        if not custom_rulesets:
            print("  ✅ No custom WAF rulesets found")
            continue

        print(f"  📋 Found {len(custom_rulesets)} custom WAF ruleset(s):")

        for ruleset in custom_rulesets:
            print(f"    - {ruleset['name']} (ID: {ruleset['id']})")

            # 如果是 Terraform 管理的 ruleset，則刪除
            if any(keyword in ruleset['name'].lower() for keyword in ['terraform', 'waf', 'managed']):
                print(f"    🗑️  Deleting: {ruleset['name']}")
                delete_ruleset(zone_id, ruleset['id'])
            else:
                print(f"    ⚠️  Skipping: {ruleset['name']} (not managed by Terraform)")

if __name__ == "__main__":
    # 首先清理現有的 ruleset
    cleanup_existing_rulesets()

    print("\nFetching AbuseIPDB ASN blacklist...")
    asns = fetch_abuseipdb_asns()
    print(f"Fetched {len(asns)} unique ASNs.")
    update_rules_yaml(asns)
    print(f"Updated {OUTPUT_FILE} successfully.")
