import sqlite3
import os

DB_PATH = os.path.join("data", "database.db")

# Expanded hotel database with real Indian hotels prioritized and detailed addresses
WORLDWIDE_HOTELS = [
    # PRIORITY: Major Indian Hotels with Real Addresses
    ("Taj Mahal Palace", "Apollo Bunder, Colaba", "Mumbai", "India", "400039", 28.3358, 77.2289, 4.8, 2500),
    ("ITC Maurya", "Diplomatic Enclave, Sardar Patel Marg", "New Delhi", "India", "110021", 28.5921, 77.2030, 4.7, 1800),
    ("The Oberoi New Delhi", "Dr. Zakir Hussain Marg, New Delhi", "New Delhi", "India", "110003", 28.6129, 77.2043, 4.7, 2200),
    ("JW Marriott Mumbai", "Juhu Tara Road, Juhu Beach", "Mumbai", "India", "400049", 19.1136, 72.8281, 4.6, 1500),
    ("Leela Palace New Delhi", "Chanakyapuri, Diplomatic Enclave", "New Delhi", "India", "110021", 28.5890, 77.1980, 4.8, 1900),
    ("Taj Lake Palace", "Pichola Lake, Udaipur", "Udaipur", "India", "313001", 24.5855, 73.7622, 4.9, 3100),
    ("Vivanta By Taj", "Whitefield, Bangalore", "Bangalore", "India", "560048", 13.0349, 77.6245, 4.5, 2800),
    ("Hyatt Regency Delhi", "Bhikaji Cama Place, Institutional Area", "New Delhi", "India", "110066", 28.5706, 77.2181, 4.6, 1400),
    ("The Westin Mumbai", "Powai Lake, Akurdi", "Mumbai", "India", "400076", 19.1136, 72.8996, 4.5, 1200),
    ("Radisson Blu Mumbai", "Mahim, Bandra", "Mumbai", "India", "400016", 19.0438, 72.8281, 4.4, 2600),
    
    # More Prominent Indian Hotels
    ("Taj Bangalore", "47/1 M.G. Road", "Bangalore", "India", "560001", 13.0333, 77.6000, 4.6, 1600),
    ("The Oberoi Mumbai", "Nariman Point", "Mumbai", "India", "400021", 18.9674, 72.8297, 4.6, 1700),
    ("Hilton Mumbai International Airport", "Andheri East", "Mumbai", "India", "400099", 19.0896, 72.8656, 4.5, 1300),
    ("Park Hyatt Delhi", "Saket, New Delhi", "New Delhi", "India", "110017", 28.5241, 77.1945, 4.7, 1500),
    ("The LaLiT New Delhi", "Barakhamba Road, Connaught Place", "New Delhi", "India", "110001", 28.6328, 77.2197, 4.6, 1200),
    ("Marriott Jaipur", "C-Block, Malviya Nagar", "Jaipur", "India", "302017", 26.9124, 75.7873, 4.5, 900),
    ("ITC Rajputana Jaipur", "Prithviraj Road, C-Scheme", "Jaipur", "India", "302003", 26.9124, 75.8118, 4.6, 800),
    ("The Leela Goa", "Mobor Beach, Cavelossim", "Goa", "India", "403731", 14.9869, 73.9563, 4.7, 1400),
    ("Taj Exotica Goa", "Benaulim Beach", "Goa", "India", "403716", 14.9869, 73.8844, 4.8, 1100),
    ("Park Hyatt Goa", "Arossim Beach", "Goa", "India", "403712", 14.9869, 73.8438, 4.6, 900),
    
    # Tier-2 Indian Cities - Hotels
    ("ITC Grand Central Mumbai", "Nariман Point", "Mumbai", "India", "400021", 18.9674, 72.8297, 4.5, 1400),
    ("Four Seasons Hotel Delhi", "Diplomatic Enclave", "New Delhi", "India", "110021", 28.5941, 77.2011, 4.8, 1300),
    ("Le Meridien Delhi", "Connaught Place", "New Delhi", "India", "110001", 28.6337, 77.2197, 4.5, 1000),
    ("Taj Samudra Bangalore", "M.G. Road", "Bangalore", "India", "560001", 13.0351, 77.5988, 4.5, 1200),
    ("Lemon Tree Hotel Pune", "Viman Nagar", "Pune", "India", "411014", 18.5628, 73.9201, 4.4, 700),
    ("Oberoi Udaipur", "Haridasji Ki Magri, East Bank Road", "Udaipur", "India", "313001", 24.5819, 73.7571, 4.7, 1200),
    ("Taj Coromandel Chennai", "Conran Smith Road, Nungambakkam", "Chennai", "India", "600034", 13.0472, 80.2549, 4.6, 1100),
    ("ITC Grand Maratha Sheraton Mumbai", "Sahar, Vile Parle", "Mumbai", "India", "400090", 19.1146, 72.8447, 4.5, 1300),
    ("Hyatt Hyderabad", "Gachibowli", "Hyderabad", "India", "500032", 17.3850, 78.4867, 4.5, 900),
    ("Taj Lake Palace Udaipur", "Lake Pichola", "Udaipur", "India", "313001", 24.5855, 73.7622, 4.9, 2000),
    
    # Budget and Mid-Range Indian Hotels
    ("The Ashok Delhi", "Diplomatic Enclave", "New Delhi", "India", "110021", 28.5885, 77.2020, 4.3, 800),
    ("Clarks Hotel Agra", "54 Taj Road", "Agra", "India", "282001", 27.1751, 78.0421, 4.4, 600),
    ("Radisson Blu Jaipur", "Tonk Road", "Jaipur", "India", "302015", 26.9265, 75.8256, 4.4, 700),
    ("Hotel Taj Mahal Agra", "Taj Ganj", "Agra", "India", "282001", 27.1735, 78.0433, 4.3, 500),
    ("Itc Welcomhotel Sheraton Kolkata", "1/2 A.J.C. Bose Road", "Kolkata", "India", "700020", 22.5644, 88.3639, 4.4, 900),
    ("The Lalit Ashok Bangalore", "Kumara Krupa Road", "Bangalore", "India", "560001", 13.0296, 77.5971, 4.4, 1000),
    ("Crowne Plaza New Delhi", "Mayur Vihar Phase-1", "New Delhi", "India", "110091", 28.5559, 77.2574, 4.3, 800),
    ("Lemon Tree Hotel Mumbai", "Vile Parle", "Mumbai", "India", "400056", 19.1194, 72.8481, 4.3, 700),
    ("Hotel Amar Jaipur", "M.I. Road", "Jaipur", "India", "302001", 26.9124, 75.8256, 4.2, 600),
    ("Golden Tulip Gurgaon", "Golf Course Road", "Gurgaon", "India", "122001", 28.4595, 77.0461, 4.3, 800),
    
    # International Hotels (Secondary Priority)
    ("The Plaza Hotel", "Fifth Avenue", "New York", "USA", "10019", 40.7656, -73.9776, 4.6, 3500),
    ("The Beverly Hills Hotel", "Sunset Boulevard", "Los Angeles", "USA", "90210", 34.0826, -118.3806, 4.7, 2800),
    ("Four Seasons Hotel San Francisco", "Market Street", "San Francisco", "USA", "94102", 37.7749, -122.4194, 4.8, 2100),
    ("Ritz Paris", "Rue Cambon", "Paris", "France", "75001", 48.8675, 2.3263, 4.9, 2600),
    ("Hotel de Crillon", "Place de la Concorde", "Paris", "France", "75008", 48.8656, 2.3213, 4.8, 2200),
    ("Savoy Hotel", "The Strand", "London", "UK", "WC2R 0EU", 51.5109, -0.1195, 4.7, 2900),
    ("Claridge's", "Brook Street", "London", "UK", "W1K 4HR", 51.5132, -0.1493, 4.8, 2100),
    ("Peninsula Hong Kong", "Salisbury Road", "Hong Kong", "Hong Kong", "0", 22.2969, 114.1738, 4.9, 2800),
    ("Mandarin Oriental Bangkok", "Rama IV Road", "Bangkok", "Thailand", "10330", 13.7563, 100.5018, 4.8, 2500),
    ("Four Seasons Singapore", "River Valley Road", "Singapore", "Singapore", "179033", 1.2882, 103.8607, 4.9, 2000),
    ("Marina Bay Sands", "Marina Bay", "Singapore", "Singapore", "018957", 1.2826, 103.8606, 4.5, 3500),
    ("Burj Al Arab", "Jumeirah Beach", "Dubai", "UAE", "0", 25.1413, 55.1855, 4.7, 3200),
    ("Park Hyatt Sydney", "Circular Quay", "Sydney", "Australia", "2000", -33.8568, 151.2153, 4.8, 2600),
    ("Copacabana Palace", "Atlantic Beach", "Rio de Janeiro", "Brazil", "20000-000", -23.0102, -43.1761, 4.8, 2200),
    ("Alvear Palace Hotel", "Avenida Alvear", "Buenos Aires", "Argentina", "1129", -34.7997, -58.3886, 4.9, 1600),
]


def seed_hotels():
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create hotels table with coordinates and postal code
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hotels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            address TEXT NOT NULL,
            city TEXT,
            country TEXT,
            postal_code TEXT,
            latitude REAL,
            longitude REAL,
            rating_avg REAL DEFAULT 0,
            total_reviews INTEGER DEFAULT 0
        );
    """)

    # Check if hotels already seeded
    count = cursor.execute("SELECT COUNT(*) FROM hotels").fetchone()[0]
    if count > 0:
        print(f"[SEED HOTELS] {count} hotels already exist. Clearing and reseeding with expanded data...")
        cursor.execute("DELETE FROM hotels")

    # Insert hotels
    cursor.executemany(
        """
        INSERT INTO hotels (name, address, city, country, postal_code, latitude, longitude, rating_avg, total_reviews)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        WORLDWIDE_HOTELS,
    )
    conn.commit()
    
    # Count by country
    india_count = cursor.execute("SELECT COUNT(*) FROM hotels WHERE LOWER(country) = 'india'").fetchone()[0]
    conn.close()

    print(f"[SEED HOTELS] Inserted {len(WORLDWIDE_HOTELS)} hotels ({india_count} Indian hotels prioritized).")


if __name__ == "__main__":
    seed_hotels()

