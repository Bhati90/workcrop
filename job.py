"""
Generate Sample Job Data for Testing

This script generates realistic sample job data that can be used for testing
the import functionality.

Usage:
    python generate_sample_jobs.py --count 50 --output jobs.json
"""

import json
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any


class SampleJobGenerator:
    """Generate sample job data"""
    
    # Sample data pools
    TITLES = [
        "वेळेरण काळवे / मिरची",
        "पेरणी कापूस",
        "तण काढणे / निंदणी",
        "फवारणी रोग",
        "कापणी कापूस",
        "पेरणी सोयाबीन",
        "तण काढणी गव्हा",
        "रोपे लावणे भाजी",
        "पाणी देणे ऊस",
        "खोड काढणे"
    ]
    
    FARMER_NAMES = [
        "राजेंद्र पाटील",
        "सुरेश कुलकर्णी",
        "विजय देशमुख",
        "शंकर जाधव",
        "रमेश शिंदे",
        "दिनेश काळे",
        "महेश ठाकरे",
        "गणेश नाईक"
    ]
    
    VILLAGES = [
        "शिरूर",
        "दौंड",
        "पाबळ",
        "येवला",
        "इंदापूर",
        "कर्जत",
        "सासवड",
        "हवेली"
    ]
    
    TALUKAS = ["पुणे", "हवेली", "दौंड", "इंदापूर", "बारामती", "शिरूर"]
    DISTRICTS = ["पुणे", "सातारा", "सोलापूर", "कोल्हापूर"]
    
    CROPS = ["कापूस", "सोयाबीन", "मका", "गव्हा", "ज्वारी", "तूर", "मिरची", "कांदा", "टोमेटो"]
    
    STATUSES = ["pending", "assigned", "in_progress", "completed"]
    CLASS_NAMES = ["fir-1", "fir-2", "fir-3", "pest-spray", "harvest"]
    
    def generate_jobs(self, count: int) -> List[Dict[str, Any]]:
        """Generate sample jobs"""
        jobs = []
        base_date = datetime.now()
        
        for i in range(1, count + 1):
            job = self.generate_single_job(i, base_date)
            jobs.append(job)
        
        return jobs
    
    def generate_single_job(self, job_id: int, base_date: datetime) -> Dict[str, Any]:
        """Generate a single job with complex data"""
        
        # Random date within next 30 days
        days_offset = random.randint(0, 30)
        start_date = base_date + timedelta(days=days_offset)
        
        # Sometimes include nulls to test handling
        include_plot_details = random.random() > 0.3
        include_farmer_phone = random.random() > 0.2
        include_location = random.random() > 0.2
        include_notes = random.random() > 0.4
        
        job = {
            "id": job_id,
            "title": random.choice(self.TITLES),
            "start_date": start_date.strftime("%Y-%m-%dT%H:%M:%S"),
            "plot_name": f"शेत {random.randint(1, 20)}" if include_plot_details else None,
            "plot_area": round(random.uniform(1, 50), 2) if include_plot_details else None,
            "plot_crop": random.choice(self.CROPS) if include_plot_details else None,
            "farmer_name": random.choice(self.FARMER_NAMES),
            "farmer_phone": self.generate_phone() if include_farmer_phone else None,
            "farmer_id": f"F{random.randint(1000, 9999)}",
            "location": self.generate_location() if include_location else None,
            "village": random.choice(self.VILLAGES),
            "taluka": random.choice(self.TALUKAS),
            "district": random.choice(self.DISTRICTS),
            "fir_id": random.randint(1, 100),
            "notes": self.generate_notes() if include_notes else None,
            "class_name": random.choice(self.CLASS_NAMES),
            "workers_required": random.randint(5, 50),
            "status": random.choice(self.STATUSES),
            "allDay": random.choice([True, False]),
        }
        
        # Sometimes add data in different formats (arrays, nested objects)
        if random.random() > 0.8:
            # Add array format for some fields
            job["farmer_phone"] = [self.generate_phone()] if job["farmer_phone"] else None
            
        if random.random() > 0.7:
            # Add nested location object
            job["location"] = {
                "address": self.generate_location(),
                "coordinates": {
                    "lat": round(random.uniform(18.0, 19.5), 6),
                    "lng": round(random.uniform(73.0, 75.0), 6)
                }
            }
        
        return job
    
    def generate_phone(self) -> str:
        """Generate Indian phone number"""
        return f"{''.join([str(random.randint(0, 9)) for _ in range(10)])}"
    
    def generate_location(self) -> str:
        """Generate location string"""
        return f"Survey No. {random.randint(1, 500)}/{random.randint(1, 10)}"
    
    def generate_notes(self) -> str:
        """Generate notes"""
        notes_options = [
            "सकाळी 7 वाजता सुरू करायचे",
            "दुपारी जेवण देणे आहे",
            "वाहतूक कंपनीकडून मिळेल",
            "पगार रोजच्या रोजी",
            "अनुभवी कामगार हवेत",
            "तातडीने कामगार हवेत",
            "2-3 दिवसाचे काम"
        ]
        return random.choice(notes_options)
    
    def save_to_file(self, jobs: List[Dict], filename: str):
        """Save jobs to JSON file"""
        output = {
            "data": jobs,
            "total": len(jobs),
            "generated_at": datetime.now().isoformat()
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        
        print(f'Generated {len(jobs)} jobs and saved to {filename}')


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate sample job data')
    parser.add_argument('--count', type=int, default=20, help='Number of jobs to generate')
    parser.add_argument('--output', default='sample_jobs.json', help='Output filename')
    
    args = parser.parse_args()
    
    generator = SampleJobGenerator()
    jobs = generator.generate_jobs(args.count)
    generator.save_to_file(jobs, args.output)


if __name__ == '__main__':
    main()