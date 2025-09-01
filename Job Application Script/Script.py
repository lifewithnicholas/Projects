import csv
import os

FILE_NAME = "job_tracker.csv"

# Ensure CSV exists
def init_file():
    if not os.path.exists(FILE_NAME):
        with open(FILE_NAME, mode="w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["Company", "Role", "Status"])  # Status: Applied, Interview, Offer, Rejected

# Add a new application
def add_application(company, role):
    with open(FILE_NAME, mode="a", newline="") as file:
        writer = csv.writer(file)
        writer.writerow([company, role, "Applied"])
    print(f"Application added: {company} - {role}")

# Update status (Interview, Offer, Rejected)
def update_status(company, role, status):
    rows = []
    updated = False
    with open(FILE_NAME, mode="r") as file:
        reader = csv.reader(file)
        rows = list(reader)

    for row in rows:
        if row[0] == company and row[1] == role:
            row[2] = status
            updated = True
            break

    with open(FILE_NAME, mode="w", newline="") as file:
        writer = csv.writer(file)
        writer.writerows(rows)

    if updated:
        print(f"Status updated: {company} - {role} → {status}")
    else:
        print("Application not found.")

# Show stats
def show_stats():
    with open(FILE_NAME, mode="r") as file:
        reader = csv.DictReader(file)
        applications = list(reader)

    total = len(applications)
    interviews = sum(1 for a in applications if a["Status"] == "Interview")
    offers = sum(1 for a in applications if a["Status"] == "Offer")
    rejections = sum(1 for a in applications if a["Status"] == "Rejected")

    print("\n--- Job Search Stats ---")
    print(f"Total Applications: {total}")
    print(f"Interviews: {interviews} ({(interviews/total*100 if total else 0):.1f}%)")
    print(f"Offers: {offers} ({(offers/interviews*100 if interviews else 0):.1f}% of interviews)")
    print(f"Rejections: {rejections} ({(rejections/total*100 if total else 0):.1f}%)")
    print("-------------------------\n")

# Example usage
if __name__ == "__main__":
    init_file()
    # add_application("Google", "Software Engineer")
    # update_status("Google", "Software Engineer", "Interview")
    # update_status("Google", "Software Engineer", "Offer")
    show_stats()
