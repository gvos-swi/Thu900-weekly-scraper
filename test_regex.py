import re

# Test the regex pattern
pattern = r"Interac e-Transfer.*received \$([0-9]+\.[0-9]{2}) from (.+?) and it has been"

test_subjects = [
    "Interac e-Transfer: You've received $25.00 from DEVON CHUN KIT LUNG and it has been automatically deposited.",
    "Interac e-Transfer: You've received $25.00 from CURTIS B HUGHESMAN and it has been automatically deposited.",
    "Interac e-Transfer: You've received $25.00 from EVAN MORGAN and it has been automatically deposited."
]

for subject in test_subjects:
    match = re.search(pattern, subject, re.IGNORECASE)
    if match:
        amount = match.group(1)
        name = match.group(2)
        print(f"✓ MATCHED: ${amount} from {name}")
    else:
        print(f"✗ FAILED: {subject[:60]}...")
