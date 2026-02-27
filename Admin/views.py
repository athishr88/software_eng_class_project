from django.shortcuts import render


def admin_dashboard(request):
    steward_flags = [
        {
            "username": "erica_92",
            "user_id": 10492,
            "reason": "Unusual free book claim frequency",
            "severity": "High",
            "status": "Open",
            "flagged_date": "Feb 21, 2026",
        },
        {
            "username": "ben_reads",
            "user_id": 7781,
            "reason": "Repeated claim attempts across listings",
            "severity": "Medium",
            "status": "Open",
            "flagged_date": "Feb 20, 2026",
        },
        {
            "username": "kavya_books",
            "user_id": 4510,
            "reason": "Possible multi account coordination",
            "severity": "Medium",
            "status": "Triage",
            "flagged_date": "Feb 18, 2026",
        },
        {
            "username": "jay_s",
            "user_id": 3394,
            "reason": "Rapid progress pattern detected",
            "severity": "Low",
            "status": "Resolved",
            "flagged_date": "Feb 16, 2026",
        },
    ]

    payment_flags = [
        {
            "username": "matt_gh",
            "user_id": 9021,
            "signal": "Multiple failed attempts then success",
            "severity": "High",
            "status": "Open",
            "flagged_date": "Feb 22, 2026",
        },
        {
            "username": "divya_shop",
            "user_id": 12011,
            "signal": "Chargeback trend above threshold",
            "severity": "High",
            "status": "Triage",
            "flagged_date": "Feb 21, 2026",
        },
        {
            "username": "sam_new",
            "user_id": 13008,
            "signal": "Mismatch in billing region signals",
            "severity": "Medium",
            "status": "Open",
            "flagged_date": "Feb 19, 2026",
        },
        {
            "username": "rachel_1",
            "user_id": 6620,
            "signal": "Refund velocity anomaly",
            "severity": "Low",
            "status": "Resolved",
            "flagged_date": "Feb 15, 2026",
        },
    ]

    recent_listings = [
        {
            "title": "The Alchemist",
            "book_id": "B 44210",
            "seller": "erica_92",
            "condition": "Like New",
            "status": "Live",
            "created_date": "Feb 23, 2026",
        },
        {
            "title": "Introduction to Algorithms",
            "book_id": "B 44204",
            "seller": "ben_reads",
            "condition": "Good",
            "status": "Pending Review",
            "created_date": "Feb 23, 2026",
        },
        {
            "title": "Clean Code",
            "book_id": "B 44198",
            "seller": "jay_s",
            "condition": "Very Good",
            "status": "Live",
            "created_date": "Feb 22, 2026",
        },
        {
            "title": "Harry Potter Box Set",
            "book_id": "B 44180",
            "seller": "kavya_books",
            "condition": "Fair",
            "status": "Hidden",
            "created_date": "Feb 21, 2026",
        },
        {
            "title": "Atomic Habits",
            "book_id": "B 44177",
            "seller": "sam_new",
            "condition": "New",
            "status": "Live",
            "created_date": "Feb 21, 2026",
        },
    ]

    context = {
        "admin_name": "Admin",
        "steward_flags": steward_flags,
        "payment_flags": payment_flags,
        "recent_listings": recent_listings,
        "metrics": {
            "total_users": "12,438",
            "active_users_30d": "4,106",
            "books_listed": "28,774",
            "books_available": "9,552",
            "orders_month": "1,284",
            "returns_month": "74",
            "open_flags": "26",
            "revenue_month": "$3,920",
            "total_users_note": "+142 this week",
            "active_users_note": "33% of total",
            "books_listed_note": "+310 today",
            "books_available_note": "In stock listings",
            "orders_month_note": "88 today",
            "returns_month_note": "5.8% return rate",
            "open_flags_note": "Needs review",
            "revenue_month_note": "Platform fees",
        },
    }
    return render(request, "dashboard/admin_dashboard.html", context)


def reports_flags(request):
    all_flags = [
        {
            "flag_id": "F1021",
            "type": "Steward Abuse",
            "target": "erica_92",
            "reason": "Unusual free book claim frequency",
            "severity": "High",
            "status": "Open",
            "date": "Feb 21, 2026",
        },
        {
            "flag_id": "F1022",
            "type": "Payment Abuse",
            "target": "matt_gh",
            "reason": "Multiple failed attempts then success",
            "severity": "High",
            "status": "Triage",
            "date": "Feb 22, 2026",
        },
        {
            "flag_id": "F1023",
            "type": "Listing Abuse",
            "target": "Book ID B44210",
            "reason": "Misleading condition description",
            "severity": "Medium",
            "status": "Open",
            "date": "Feb 20, 2026",
        },
        {
            "flag_id": "F1024",
            "type": "User Report",
            "target": "ben_reads",
            "reason": "Inappropriate listing language",
            "severity": "Low",
            "status": "Resolved",
            "date": "Feb 18, 2026",
        },
    ]

    context = {
        "admin_name": "Admin",
        "all_flags": all_flags,
    }
    return render(request, "dashboard/reports_flags.html", context)
