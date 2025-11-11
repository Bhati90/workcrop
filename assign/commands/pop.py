from django.core.management.base import BaseCommand
from assign.models import Job, Mukadam, MukadamBid, JobAssignment, JobStatusHistory
from django.contrib.auth.models import User
import random

class Command(BaseCommand):
    help = 'Create test job assignments and bids for demo purposes'

    def add_arguments(self, parser):
        parser.add_argument('--job-id', type=str, help='Specific job ID to assign')
        parser.add_argument('--all-jobs', action='store_true', help='Assign all confirmed jobs')

    def handle(self, *args, **options):
        try:
            # Get all active mukadams
            mukadams = list(Mukadam.objects.filter(is_active=True))
            if len(mukadams) == 0:
                self.stdout.write(self.style.ERROR('No active mukadams found. Please add mukadams first.'))
                return

            self.stdout.write(f'Found {len(mukadams)} active mukadams')

            # Get jobs to assign
            if options['job_id']:
                jobs = Job.objects.filter(id=options['job_id'], status='confirmed')
            elif options['all_jobs']:
                jobs = Job.objects.filter(status='confirmed')
            else:
                # Get the latest confirmed job
                jobs = Job.objects.filter(status='confirmed').order_by('-confirmed_at')[:1]

            if not jobs:
                self.stdout.write(self.style.ERROR('No confirmed jobs found to assign'))
                return

            system_user, _ = User.objects.get_or_create(
                username='system',
                defaults={'email': 'system@farmops.com', 'is_active': False}
            )

            for job in jobs:
                self.stdout.write(f'\n🎯 Processing Job: {job.farmer.name} - {job.activity.name}')
                self.stdout.write(f'   Farm Size: {job.farm_size_acres} acres')
                self.stdout.write(f'   Farmer Price: ₹{job.farmer_price_per_acre}/acre')
                
                # 1. Assign job to all mukadams
                assignments_created = 0
                for mukadam in mukadams:
                    assignment, created = JobAssignment.objects.get_or_create(
                        job=job,
                        mukadam=mukadam
                    )
                    if created:
                        assignments_created += 1
                        self.stdout.write(f'   ✅ Assigned to: {mukadam.name}')
                
                # 2. Update job status to bidding
                job.status = 'bidding'
                job.save()
                
                # 3. Create status history
                JobStatusHistory.objects.create(
                    job=job,
                    from_status='confirmed',
                    to_status='bidding',
                    changed_by=system_user,
                    notes=f'Assigned to {assignments_created} mukadams via test script'
                )

                # 4. Create realistic bids from mukadams
                farmer_price = float(job.farmer_price_per_acre)
                bid_variations = [
                    -200, -150, -100, -50, 0, 50  # Different pricing strategies
                ]
                
                responses = ['interested', 'interested', 'interested', 'interested', 'interested', 'declined']
                
                for i, mukadam in enumerate(mukadams):
                    response_type = responses[i % len(responses)]
                    
                    if response_type == 'interested':
                        # Create competitive bid
                        base_variation = bid_variations[i % len(bid_variations)]
                        additional_random = random.randint(-25, 25)
                        bid_price = max(farmer_price + base_variation + additional_random, farmer_price * 0.7)
                        
                        # Get activity rate if available
                        activity_rate = mukadam.activity_rates.filter(
                            activity=job.activity, is_available=True
                        ).first()
                        
                        if activity_rate:
                            # Use mukadam's preset rate with small variation
                            bid_price = float(activity_rate.rate_per_acre) + random.randint(-50, 50)
                        
                        estimated_hours = random.randint(6, 12)
                        comments_options = [
                            f"Available with {mukadam.number_of_labourers} experienced workers. Can start early morning.",
                            f"Experienced team ready. We specialize in {job.activity.name}.",
                            f"Quality work guaranteed. Team of {mukadam.number_of_labourers} skilled labourers.",
                            f"We can complete in {estimated_hours} hours with our efficient team.",
                            "Premium service with quality assurance. Long-term partnership preferred.",
                            f"Local team from {mukadam.location}. Familiar with area conditions."
                        ]
                        
                        bid, created = MukadamBid.objects.update_or_create(
                            job=job,
                            mukadam=mukadam,
                            defaults={
                                'status': 'interested',
                                'bid_price_per_acre': round(bid_price, 2),
                                'estimated_duration_hours': estimated_hours,
                                'comments': comments_options[i % len(comments_options)],
                                'responded_at': job.confirmed_at
                            }
                        )
                        
                        self.stdout.write(f'   💰 {mukadam.name}: ₹{bid_price:.2f}/acre ({estimated_hours}h)')
                        
                    else:
                        # Create declined bid
                        decline_reasons = [
                            "Team already committed for those dates.",
                            "Location too far from our base.",
                            "Workload full for next week.",
                            "Equipment maintenance scheduled.",
                        ]
                        
                        bid, created = MukadamBid.objects.update_or_create(
                            job=job,
                            mukadam=mukadam,
                            defaults={
                                'status': 'declined',
                                'comments': decline_reasons[i % len(decline_reasons)],
                                'responded_at': job.confirmed_at
                            }
                        )
                        
                        self.stdout.write(f'   ❌ {mukadam.name}: Declined - {bid.comments}')

                # 5. Show bid summary
                interested_bids = MukadamBid.objects.filter(job=job, status='interested').order_by('bid_price_per_acre')
                if interested_bids:
                    lowest_bid = interested_bids.first()
                    highest_bid = interested_bids.last()
                    
                    self.stdout.write(f'\n   📊 BID SUMMARY:')
                    self.stdout.write(f'   Farmer Price: ₹{farmer_price}/acre')
                    self.stdout.write(f'   Lowest Bid: ₹{lowest_bid.bid_price_per_acre}/acre ({lowest_bid.mukadam.name})')
                    self.stdout.write(f'   Highest Bid: ₹{highest_bid.bid_price_per_acre}/acre ({highest_bid.mukadam.name})')
                    
                    potential_savings = (farmer_price - float(lowest_bid.bid_price_per_acre)) * float(job.farm_size_acres)
                    if potential_savings > 0:
                        self.stdout.write(f'   💰 Potential Savings: ₹{potential_savings:,.2f}')
                    else:
                        extra_cost = abs(potential_savings)
                        self.stdout.write(f'   📈 Premium Cost: ₹{extra_cost:,.2f}')

            self.stdout.write(self.style.SUCCESS('\n🎉 Test data creation completed!'))
            self.stdout.write('\n📋 Next steps:')
            self.stdout.write('1. Go to Job Management → Bidding tab')
            self.stdout.write('2. Click on a job to see all bids')
            self.stdout.write('3. Compare prices and select the best mukadam')
            self.stdout.write('4. Finalize to complete the workflow')

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))