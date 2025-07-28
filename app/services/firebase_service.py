# ==============================================================================
# Firebase Database Service
# ------------------------------------------------------------------------------
# This file handles all communication with the Google Firestore database.
# This version includes the new, automatic seeder for the NeetCode 150 plan.
# ==============================================================================

from flask import current_app
from firebase_admin import firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from werkzeug.security import generate_password_hash
import datetime

# This helper function makes the code cleaner by getting the db connection
def _get_db():
    return current_app.config['DB']

# --- User & Authentication Functions ---
def get_user_data(username):
    if not username: return None
    db = _get_db()
    doc_ref = db.collection('users').document(username)
    doc = doc_ref.get()
    return doc.to_dict() if doc.exists else None

def get_user_by_email(email):
    db = _get_db()
    users_ref = db.collection('users').where(filter=FieldFilter('email', '==', email)).limit(1)
    docs = users_ref.stream()
    for doc in docs:
        return doc.to_dict()
    return None

def create_unverified_user(username, email, otp):
    db = _get_db()
    user_ref = db.collection('users').document(username)
    expiration = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=10)
    user_ref.set({
        'leetcode_username': username, 'email': email, 'is_verified': False,
        'otp': otp, 'otp_expires': expiration
    })

def verify_user_and_set_password(username, password_hash):
    db = _get_db()
    user_ref = db.collection('users').document(username)
    user_ref.update({
        'password_hash': password_hash, 'is_verified': True,
        'otp': firestore.DELETE_FIELD, 'otp_expires': firestore.DELETE_FIELD
    })

def set_password_reset_otp(username, otp):
    db = _get_db()
    user_ref = db.collection('users').document(username)
    expiration = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=10)
    user_ref.update({'reset_otp': otp, 'reset_otp_expires': expiration})

def reset_password(username, new_password_hash):
    db = _get_db()
    user_ref = db.collection('users').document(username)
    user_ref.update({
        'password_hash': new_password_hash,
        'reset_otp': firestore.DELETE_FIELD, 'reset_otp_expires': firestore.DELETE_FIELD
    })

def delete_user_account(username):
    db = _get_db()
    try:
        db.collection('users').document(username).delete()
        return True
    except Exception as e:
        print(f"Error deleting user {username}: {e}")
        return False

# --- Friends Functions ---
def add_friend(main_username, friend_username):
    if not main_username or not friend_username or main_username == friend_username: return False
    db = _get_db()
    user_ref = db.collection('users').document(main_username)
    user_ref.update({'friends': firestore.ArrayUnion([friend_username])})
    return True

def remove_friend(main_username, friend_username):
    if not main_username or not friend_username: return False
    db = _get_db()
    user_ref = db.collection('users').document(main_username)
    user_ref.update({'friends': firestore.ArrayRemove([friend_username])})
    return True

def get_friends(main_username):
    user_data = get_user_data(main_username)
    return user_data.get('friends', []) if user_data else []


# --- Challenge Functions ---
def create_challenge(challenge_data):
    db = _get_db()
    try:
        db.collection('challenges').add(challenge_data)
        return True
    except Exception as e:
        print(f"Error creating challenge: {e}")
        return False

def get_user_challenges(username):
    db = _get_db()
    challenges_ref = db.collection('challenges').where(filter=FieldFilter('status', '==', 'active'))
    docs = challenges_ref.stream()
    user_challenges = []
    for doc in docs:
        challenge_data = doc.to_dict()
        if username in challenge_data.get('participants', {}):
            challenge_data['id'] = doc.id
            user_challenges.append(challenge_data)
    return user_challenges

def update_challenge_participant_status(challenge_id, username, new_status):
    db = _get_db()
    challenge_ref = db.collection('challenges').document(challenge_id)
    challenge_ref.update({f'participants.{username}.status': new_status})
    return True

def delete_challenge(challenge_id):
    db = _get_db()
    try:
        db.collection('challenges').document(challenge_id).delete()
        return True
    except Exception as e:
        print(f"Error deleting challenge {challenge_id}: {e}")
        return False

def get_challenge_by_id(challenge_id):
    db = _get_db()
    doc = db.collection('challenges').document(challenge_id).get()
    if doc.exists:
        challenge_data = doc.to_dict()
        challenge_data['id'] = doc.id
        return challenge_data
    return None

def update_challenge_details(challenge_id, updated_data):
    db = _get_db()
    try:
        db.collection('challenges').document(challenge_id).update(updated_data)
        return True
    except Exception as e:
        print(f"Error updating challenge {challenge_id}: {e}")
        return False

# --- Study Plan Functions ---
def get_study_plan_questions():
    """Fetches the entire list of curated study plan questions, ordered correctly."""
    db = _get_db()
    docs = db.collection('study_plan_questions').order_by('order').stream()
    return [doc.to_dict() for doc in docs]

def get_or_initialize_user_study_plan(username):
    """Gets a user's study plan progress. If it doesn't exist, creates it."""
    db = _get_db()
    user_ref = db.collection('users').document(username)
    user_doc = user_ref.get()
    if user_doc.exists:
        user_data = user_doc.to_dict()
        if 'study_plan_progress' in user_data:
            return user_data['study_plan_progress']
        else:
            initial_progress = {'current_question_index': 0}
            user_ref.update({'study_plan_progress': initial_progress})
            return initial_progress
    return None

def advance_user_study_plan(username, current_index):
    """Increments the user's current question index by 1."""
    db = _get_db()
    user_ref = db.collection('users').document(username)
    user_ref.update({'study_plan_progress.current_question_index': firestore.Increment(1)})
    return True

# --- Database Seeder ---
def _create_seed_user(username, email, password):
    db = _get_db()
    password_hash = generate_password_hash(password)
    db.collection('users').document(username).set({
        'leetcode_username': username, 'email': email,
        'password_hash': password_hash, 'is_verified': True, 'friends': []
    })

def seed_database():
    db = _get_db()
    if db.collection('users').document('testuser1').get().exists:
        return "Database has already been seeded. No action taken."
    try:
        _create_seed_user('testuser1', 'testuser1@example.com', 'password123')
        _create_seed_user('testuser2', 'testuser2@example.com', 'password123')
        db.collection('users').document('testuser1').update({'friends': firestore.ArrayUnion(['testuser2'])})
        db.collection('users').document('testuser2').update({'friends': firestore.ArrayUnion(['testuser1'])})
        challenge1_data = {
            'creatorUsername': 'testuser2', 'title': 'Sample Invitation',
            'description': 'A test challenge for testuser1.',
            'expiresAt': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=3),
            'status': 'active', 'problems': [{'title': 'Two Sum', 'titleSlug': 'two-sum'}],
            'participants': {'testuser2': {'status': 'accepted'}, 'testuser1': {'status': 'invited'}}
        }
        db.collection('challenges').add(challenge1_data)
        return "Database seeded successfully!"
    except Exception as e:
        return f"An error occurred during seeding: {e}"

# --- NEW: NeetCode 150 Data & Seeder Function ---
NEETCODE_150_QUESTIONS = [
    {"order": 1, "topic": "Arrays & Hashing", "title": "Contains Duplicate", "titleSlug": "contains-duplicate", "difficulty": "Easy", "videoSolution": "https://www.youtube.com/watch?v=3OamzN90kPg"},
    {"order": 2, "topic": "Arrays & Hashing", "title": "Valid Anagram", "titleSlug": "valid-anagram", "difficulty": "Easy", "videoSolution": "https://www.youtube.com/watch?v=9UtInBqnCgA"},
    {"order": 3, "topic": "Arrays & Hashing", "title": "Two Sum", "titleSlug": "two-sum", "difficulty": "Easy", "videoSolution": "https://www.youtube.com/watch?v=KLlXCFG5TnA"},
    {"order": 4, "topic": "Arrays & Hashing", "title": "Group Anagrams", "titleSlug": "group-anagrams", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=vzdNOK2oB2E"},
    {"order": 5, "topic": "Arrays & Hashing", "title": "Top K Frequent Elements", "titleSlug": "top-k-frequent-elements", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=YPTqKIgVk-k"},
    {"order": 6, "topic": "Arrays & Hashing", "title": "Product of Array Except Self", "titleSlug": "product-of-array-except-self", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=bNvIQI2wAjk"},
    {"order": 7, "topic": "Arrays & Hashing", "title": "Valid Sudoku", "titleSlug": "valid-sudoku", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=TjfxOhDE3oM"},
    {"order": 8, "topic": "Arrays & Hashing", "title": "Encode and Decode Strings", "titleSlug": "encode-and-decode-strings", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=B1k_sxOSgv8"},
    {"order": 9, "topic": "Arrays & Hashing", "title": "Longest Consecutive Sequence", "titleSlug": "longest-consecutive-sequence", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=P6RZZMu_maU"},
    {"order": 10, "topic": "Two Pointers", "title": "Valid Palindrome", "titleSlug": "valid-palindrome", "difficulty": "Easy", "videoSolution": "https://www.youtube.com/watch?v=jJXJ16kPFWg"},
    {"order": 11, "topic": "Two Pointers", "title": "Two Sum II - Input Array Is Sorted", "titleSlug": "two-sum-ii-input-array-is-sorted", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=cQ1Oz4ckceM"},
    {"order": 12, "topic": "Two Pointers", "title": "3Sum", "titleSlug": "3sum", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=jzZfxsIWhSc"},
    {"order": 13, "topic": "Two Pointers", "title": "Container With Most Water", "titleSlug": "container-with-most-water", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=UuiTKBwPgAo"},
    {"order": 14, "topic": "Two Pointers", "title": "Trapping Rain Water", "titleSlug": "trapping-rain-water", "difficulty": "Hard", "videoSolution": "https://www.youtube.com/watch?v=ZI2z5pq0TqA"},
    {"order": 15, "topic": "Sliding Window", "title": "Best Time to Buy and Sell Stock", "titleSlug": "best-time-to-buy-and-sell-stock", "difficulty": "Easy", "videoSolution": "https://www.youtube.com/watch?v=1pkOgD63yB0"},
    {"order": 16, "topic": "Sliding Window", "title": "Longest Substring Without Repeating Characters", "titleSlug": "longest-substring-without-repeating-characters", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=wiGpQwVHdE0"},
    {"order": 17, "topic": "Sliding Window", "title": "Longest Repeating Character Replacement", "titleSlug": "longest-repeating-character-replacement", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=gqXU1UyA8pk"},
    {"order": 18, "topic": "Sliding Window", "title": "Permutation in String", "titleSlug": "permutation-in-string", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=UbyhOgBN834"},
    {"order": 19, "topic": "Sliding Window", "title": "Minimum Window Substring", "titleSlug": "minimum-window-substring", "difficulty": "Hard", "videoSolution": "https://www.youtube.com/watch?v=jSto0O4AJbM"},
    {"order": 20, "topic": "Sliding Window", "title": "Sliding Window Maximum", "titleSlug": "sliding-window-maximum", "difficulty": "Hard", "videoSolution": "https://www.youtube.com/watch?v=DfljaUwZsOk"},
    {"order": 21, "topic": "Stack", "title": "Valid Parentheses", "titleSlug": "valid-parentheses", "difficulty": "Easy", "videoSolution": "https://www.youtube.com/watch?v=WTzjTskfAuQ"},
    {"order": 22, "topic": "Stack", "title": "Min Stack", "titleSlug": "min-stack", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=WxZ58x-64kM"},
    {"order": 23, "topic": "Stack", "title": "Evaluate Reverse Polish Notation", "titleSlug": "evaluate-reverse-polish-notation", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=iu00C2c-gOE"},
    {"order": 24, "topic": "Stack", "title": "Generate Parentheses", "titleSlug": "generate-parentheses", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=s9fokUqJ76A"},
    {"order": 25, "topic": "Stack", "title": "Daily Temperatures", "titleSlug": "daily-temperatures", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=cTBiBSnjO3c"},
    {"order": 26, "topic": "Stack", "title": "Car Fleet", "titleSlug": "car-fleet", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=Pr6T-3yB9lI"},
    {"order": 27, "topic": "Stack", "title": "Largest Rectangle in Histogram", "titleSlug": "largest-rectangle-in-histogram", "difficulty": "Hard", "videoSolution": "https://www.youtube.com/watch?v=zx5Sw9130L0"},
    {"order": 28, "topic": "Binary Search", "title": "Binary Search", "titleSlug": "binary-search", "difficulty": "Easy", "videoSolution": "https://www.youtube.com/watch?v=s4DPM8ct1pI"},
    {"order": 29, "topic": "Binary Search", "title": "Search a 2D Matrix", "titleSlug": "search-a-2d-matrix", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=Ber2pi2C0j0"},
    {"order": 30, "topic": "Binary Search", "title": "Koko Eating Bananas", "titleSlug": "koko-eating-bananas", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=U2SozAs9RzA"},
    {"order": 31, "topic": "Binary Search", "title": "Search in Rotated Sorted Array", "titleSlug": "search-in-rotated-sorted-array", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=U8XENwh8Oy8"},
    {"order": 32, "topic": "Binary Search", "title": "Find Minimum in Rotated Sorted Array", "titleSlug": "find-minimum-in-rotated-sorted-array", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=nIVW4P8b1VA"},
    {"order": 33, "topic": "Binary Search", "title": "Time Based Key-Value Store", "titleSlug": "time-based-key-value-store", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=fu2cD_6K8H4"},
    {"order": 34, "topic": "Binary Search", "title": "Median of Two Sorted Arrays", "titleSlug": "median-of-two-sorted-arrays", "difficulty": "Hard", "videoSolution": "https://www.youtube.com/watch?v=q6IEA26hvX8"},
    {"order": 35, "topic": "Linked List", "title": "Reverse Linked List", "titleSlug": "reverse-linked-list", "difficulty": "Easy", "videoSolution": "https://www.youtube.com/watch?v=G0_I-ZF0S38"},
    {"order": 36, "topic": "Linked List", "title": "Merge Two Sorted Lists", "titleSlug": "merge-two-sorted-lists", "difficulty": "Easy", "videoSolution": "https://www.youtube.com/watch?v=XIdigk956u0"},
    {"order": 37, "topic": "Linked List", "title": "Reorder List", "titleSlug": "reorder-list", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=S5bfAoQ-KJo"},
    {"order": 38, "topic": "Linked List", "title": "Remove Nth Node From End of List", "titleSlug": "remove-nth-node-from-end-of-list", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=XVuQxVej6y8"},
    {"order": 39, "topic": "Linked List", "title": "Copy List with Random Pointer", "titleSlug": "copy-list-with-random-pointer", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=5Y2EiZST97Y"},
    {"order": 40, "topic": "Linked List", "title": "Add Two Numbers", "titleSlug": "add-two-numbers", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=wgFPrzT-u_w"},
    {"order": 41, "topic": "Linked List", "title": "Linked List Cycle", "titleSlug": "linked-list-cycle", "difficulty": "Easy", "videoSolution": "https://www.youtube.com/watch?v=gBTe7lFR3vc"},
    {"order": 42, "topic": "Linked List", "title": "Find the Duplicate Number", "titleSlug": "find-the-duplicate-number", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=wjYubSBPo2k"},
    {"order": 43, "topic": "Linked List", "title": "LRU Cache", "titleSlug": "lru-cache", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=7ABFKpk2hD4"},
    {"order": 44, "topic": "Linked List", "title": "Merge k Sorted Lists", "titleSlug": "merge-k-sorted-lists", "difficulty": "Hard", "videoSolution": "https://www.youtube.com/watch?v=q5a5OiGbT6Q"},
    {"order": 45, "topic": "Linked List", "title": "Reverse Nodes in k-Group", "titleSlug": "reverse-nodes-in-k-group", "difficulty": "Hard", "videoSolution": "https://www.youtube.com/watch?v=1UOPsfP85V4"},
    {"order": 46, "topic": "Trees", "title": "Invert Binary Tree", "titleSlug": "invert-binary-tree", "difficulty": "Easy", "videoSolution": "https://www.youtube.com/watch?v=OnSn2XEQ4MY"},
    {"order": 47, "topic": "Trees", "title": "Maximum Depth of Binary Tree", "titleSlug": "maximum-depth-of-binary-tree", "difficulty": "Easy", "videoSolution": "https://www.youtube.com/watch?v=hTM3phVI6YQ"},
    {"order": 48, "topic": "Trees", "title": "Diameter of Binary Tree", "titleSlug": "diameter-of-binary-tree", "difficulty": "Easy", "videoSolution": "https://www.youtube.com/watch?v=bkSod-R1BvE"},
    {"order": 49, "topic": "Trees", "title": "Balanced Binary Tree", "titleSlug": "balanced-binary-tree", "difficulty": "Easy", "videoSolution": "https://www.youtube.com/watch?v=QfJsau0A2EE"},
    {"order": 50, "topic": "Trees", "title": "Same Tree", "titleSlug": "same-tree", "difficulty": "Easy", "videoSolution": "https://www.youtube.com/watch?v=vRbbcKXCxOw"},
    {"order": 51, "topic": "Trees", "title": "Subtree of Another Tree", "titleSlug": "subtree-of-another-tree", "difficulty": "Easy", "videoSolution": "https://www.youtube.com/watch?v=E36O5SWp-LE"},
    {"order": 52, "topic": "Trees", "title": "Lowest Common Ancestor of a Binary Search Tree", "titleSlug": "lowest-common-ancestor-of-a-binary-search-tree", "difficulty": "Easy", "videoSolution": "https://www.youtube.com/watch?v=gs2LMfuOR9k"},
    {"order": 53, "topic": "Trees", "title": "Binary Tree Level Order Traversal", "titleSlug": "binary-tree-level-order-traversal", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=6ZnyEApgFYg"},
    {"order": 54, "topic": "Trees", "title": "Binary Tree Right Side View", "titleSlug": "binary-tree-right-side-view", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=d4zLyf32e3I"},
    {"order": 55, "topic": "Trees", "title": "Count Good Nodes in Binary Tree", "titleSlug": "count-good-nodes-in-binary-tree", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=7cp5imvDzl4"},
    {"order": 56, "topic": "Trees", "title": "Validate Binary Search Tree", "titleSlug": "validate-binary-search-tree", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=s6ATEkipzow"},
    {"order": 57, "topic": "Trees", "title": "Kth Smallest Element in a BST", "titleSlug": "kth-smallest-element-in-a-bst", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=5LUXSvjmGCw"},
    {"order": 58, "topic": "Trees", "title": "Construct Binary Tree from Preorder and Inorder Traversal", "titleSlug": "construct-binary-tree-from-preorder-and-inorder-traversal", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=ihj4IQGZ2zc"},
    {"order": 59, "topic": "Trees", "title": "Binary Tree Maximum Path Sum", "titleSlug": "binary-tree-maximum-path-sum", "difficulty": "Hard", "videoSolution": "https://www.youtube.com/watch?v=Hr5cWUld4vU"},
    {"order": 60, "topic": "Trees", "title": "Serialize and Deserialize Binary Tree", "titleSlug": "serialize-and-deserialize-binary-tree", "difficulty": "Hard", "videoSolution": "https://www.youtube.com/watch?v=u4JAi2JJhI8"},
    {"order": 61, "topic": "Tries", "title": "Implement Trie (Prefix Tree)", "titleSlug": "implement-trie-prefix-tree", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=oobqoCJlHA0"},
    {"order": 62, "topic": "Tries", "title": "Design Add and Search Words Data Structure", "titleSlug": "design-add-and-search-words-data-structure", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=BTf05gs_jwY"},
    {"order": 63, "topic": "Tries", "title": "Word Search II", "titleSlug": "word-search-ii", "difficulty": "Hard", "videoSolution": "https://www.youtube.com/watch?v=asbcE9mZz_U"},
    {"order": 64, "topic": "Heap / Priority Queue", "title": "Kth Largest Element in a Stream", "titleSlug": "kth-largest-element-in-a-stream", "difficulty": "Easy", "videoSolution": "https://www.youtube.com/watch?v=hW8PrQrvMNc"},
    {"order": 65, "topic": "Heap / Priority Queue", "title": "Last Stone Weight", "titleSlug": "last-stone-weight", "difficulty": "Easy", "videoSolution": "https://www.youtube.com/watch?v=B-Cqbfb7v1Y"},
    {"order": 66, "topic": "Heap / Priority Queue", "title": "K Closest Points to Origin", "titleSlug": "k-closest-points-to-origin", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=rI2EBUEMfTk"},
    {"order": 67, "topic": "Heap / Priority Queue", "title": "Kth Largest Element in an Array", "titleSlug": "kth-largest-element-in-an-array", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=XEmy13g1Qxc"},
    {"order": 68, "topic": "Heap / Priority Queue", "title": "Task Scheduler", "titleSlug": "task-scheduler", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=s8p8ukTyA2I"},
    {"order": 69, "topic": "Heap / Priority Queue", "title": "Design Twitter", "titleSlug": "design-twitter", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=pNichitDD2E"},
    {"order": 70, "topic": "Heap / Priority Queue", "title": "Find Median from Data Stream", "titleSlug": "find-median-from-data-stream", "difficulty": "Hard", "videoSolution": "https://www.youtube.com/watch?v=itmhHWaHupI"},
    {"order": 71, "topic": "Backtracking", "title": "Subsets", "titleSlug": "subsets", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=REOH22Xwdkk"},
    {"order": 72, "topic": "Backtracking", "title": "Combination Sum", "titleSlug": "combination-sum", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=GBKI9VSKdGg"},
    {"order": 73, "topic": "Backtracking", "title": "Permutations", "titleSlug": "permutations", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=s7AvT7cGdSo"},
    {"order": 74, "topic": "Backtracking", "title": "Subsets II", "titleSlug": "subsets-ii", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=Vn2v6ajA7U0"},
    {"order": 75, "topic": "Backtracking", "title": "Combination Sum II", "titleSlug": "combination-sum-ii", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=rSA3t6BDDwg"},
    {"order": 76, "topic": "Backtracking", "title": "Word Search", "titleSlug": "word-search", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=pfiQ_PS1g8E"},
    {"order": 77, "topic": "Backtracking", "title": "Palindrome Partitioning", "titleSlug": "palindrome-partitioning", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=3I3l-x9E_gQ"},
    {"order": 78, "topic": "Backtracking", "title": "Letter Combinations of a Phone Number", "titleSlug": "letter-combinations-of-a-phone-number", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=0snEunUacZY"},
    {"order": 79, "topic": "Backtracking", "title": "N-Queens", "titleSlug": "n-queens", "difficulty": "Hard", "videoSolution": "https://www.youtube.com/watch?v=i05Ju7AftcM"},
    {"order": 80, "topic": "Graphs", "title": "Number of Islands", "titleSlug": "number-of-islands", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=pV2kpPD66nE"},
    {"order": 81, "topic": "Graphs", "title": "Clone Graph", "titleSlug": "clone-graph", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=mQeF6bN8hMk"},
    {"order": 82, "topic": "Graphs", "title": "Max Area of Island", "titleSlug": "max-area-of-island", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=iJGr1OtmH0c"},
    {"order": 83, "topic": "Graphs", "title": "Pacific Atlantic Water Flow", "titleSlug": "pacific-atlantic-water-flow", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=s-VkcjHqkGI"},
    {"order": 84, "topic": "Graphs", "title": "Surrounded Regions", "titleSlug": "surrounded-regions", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=9z2BunfoZ5Y"},
    {"order": 85, "topic": "Graphs", "title": "Rotting Oranges", "titleSlug": "rotting-oranges", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=y704fEOx0s0"},
    {"order": 86, "topic": "Graphs", "title": "Walls and Gates", "titleSlug": "walls-and-gates", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=e69C6xhiSQE"},
    {"order": 87, "topic": "Graphs", "title": "Course Schedule", "titleSlug": "course-schedule", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=A2bjS9EGA2s"},
    {"order": 88, "topic": "Graphs", "title": "Course Schedule II", "titleSlug": "course-schedule-ii", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=Akt3glAwyfY"},
    {"order": 89, "topic": "Graphs", "title": "Redundant Connection", "titleSlug": "redundant-connection", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=4hJ721ce010"},
    {"order": 90, "topic": "Graphs", "title": "Number of Connected Components in an Undirected Graph", "titleSlug": "number-of-connected-components-in-an-undirected-graph", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=8f1A64_Rsf4"},
    {"order": 91, "topic": "Graphs", "title": "Graph Valid Tree", "titleSlug": "graph-valid-tree", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=bXsUuownnoQ"},
    {"order": 92, "topic": "Advanced Graphs", "title": "Reconstruct Itinerary", "titleSlug": "reconstruct-itinerary", "difficulty": "Hard", "videoSolution": "https://www.youtube.com/watch?v=4C29_ClV60"},
    {"order": 93, "topic": "Advanced Graphs", "title": "Min Cost to Connect All Points", "titleSlug": "min-cost-to-connect-all-points", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=f7JOBJqL-g8"},
    {"order": 94, "topic": "Advanced Graphs", "title": "Network Delay Time", "titleSlug": "network-delay-time", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=EaphyqKU4PQ"},
    {"order": 95, "topic": "Advanced Graphs", "title": "Swim in Rising Water", "titleSlug": "swim-in-rising-water", "difficulty": "Hard", "videoSolution": "https://www.youtube.com/watch?v=amvrKlMLuG8"},
    {"order": 96, "topic": "Advanced Graphs", "title": "Alien Dictionary", "titleSlug": "alien-dictionary", "difficulty": "Hard", "videoSolution": "https://www.youtube.com/watch?v=U3N_je7-pgQ"},
    {"order": 97, "topic": "Advanced Graphs", "title": "Cheapest Flights Within K Stops", "titleSlug": "cheapest-flights-within-k-stops", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=5eIK3zUdYmE"},
    {"order": 98, "topic": "1-D Dynamic Programming", "title": "Climbing Stairs", "titleSlug": "climbing-stairs", "difficulty": "Easy", "videoSolution": "https://www.youtube.com/watch?v=Y0lT9Fck7qI"},
    {"order": 99, "topic": "1-D Dynamic Programming", "title": "Min Cost Climbing Stairs", "titleSlug": "min-cost-climbing-stairs", "difficulty": "Easy", "videoSolution": "https://www.youtube.com/watch?v=ktcwiCoWbzM"},
    {"order": 100, "topic": "1-D Dynamic Programming", "title": "House Robber", "titleSlug": "house-robber", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=73r3KWiEvyk"},
    {"order": 101, "topic": "1-D Dynamic Programming", "title": "House Robber II", "titleSlug": "house-robber-ii", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=rWAJCfYYowG"},
    {"order": 102, "topic": "1-D Dynamic Programming", "title": "Longest Palindromic Substring", "titleSlug": "longest-palindromic-substring", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=XYQe_kAWB5g"},
    {"order": 103, "topic": "1-D Dynamic Programming", "title": "Palindromic Substrings", "titleSlug": "palindromic-substrings", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=4RACzI5-du8"},
    {"order": 104, "topic": "1-D Dynamic Programming", "title": "Decode Ways", "titleSlug": "decode-ways", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=6aEyTj_6ris"},
    {"order": 105, "topic": "1-D Dynamic Programming", "title": "Coin Change", "titleSlug": "coin-change", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=H9bfqozjoqs"},
    {"order": 106, "topic": "1-D Dynamic Programming", "title": "Maximum Product Subarray", "titleSlug": "maximum-product-subarray", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=lXVy6YWFcRM"},
    {"order": 107, "topic": "1-D Dynamic Programming", "title": "Word Break", "titleSlug": "word-break", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=Sx9NNgInc3A"},
    {"order": 108, "topic": "1-D Dynamic Programming", "title": "Longest Increasing Subsequence", "titleSlug": "longest-increasing-subsequence", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=cjWnW0hdF1Y"},
    {"order": 109, "topic": "1-D Dynamic Programming", "title": "Partition Equal Subset Sum", "titleSlug": "partition-equal-subset-sum", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=IsvocB5BJhw"},
    {"order": 110, "topic": "2-D Dynamic Programming", "title": "Unique Paths", "titleSlug": "unique-paths", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=t_f0nwwdg5o"},
    {"order": 111, "topic": "2-D Dynamic Programming", "title": "Longest Common Subsequence", "titleSlug": "longest-common-subsequence", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=Ua0GhsJslWM"},
    {"order": 112, "topic": "2-D Dynamic Programming", "title": "Best Time to Buy and Sell Stock with Cooldown", "titleSlug": "best-time-to-buy-and-sell-stock-with-cooldown", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=I7j0F7AHpb8"},
    {"order": 113, "topic": "2-D Dynamic Programming", "title": "Coin Change II", "titleSlug": "coin-change-ii", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=M2med-Bv4I0"},
    {"order": 114, "topic": "2-D Dynamic Programming", "title": "Target Sum", "titleSlug": "target-sum", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=gqX-S-g3i_I"},
    {"order": 115, "topic": "2-D Dynamic Programming", "title": "Interleaving String", "titleSlug": "interleaving-string", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=3Rw3p9LrgvE"},
    {"order": 116, "topic": "2-D Dynamic Programming", "title": "Longest Increasing Path in a Matrix", "titleSlug": "longest-increasing-path-in-a-matrix", "difficulty": "Hard", "videoSolution": "https://www.youtube.com/watch?v=wCc_nd-MvpI"},
    {"order": 117, "topic": "2-D Dynamic Programming", "title": "Distinct Subsequences", "titleSlug": "distinct-subsequences", "difficulty": "Hard", "videoSolution": "https://www.youtube.com/watch?v=bppUfx3u04"},
    {"order": 118, "topic": "2-D Dynamic Programming", "title": "Edit Distance", "titleSlug": "edit-distance", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=XYi2-LPrwm4"},
    {"order": 119, "topic": "2-D Dynamic Programming", "title": "Burst Balloons", "titleSlug": "burst-balloons", "difficulty": "Hard", "videoSolution": "https://www.youtube.com/watch?v=VFskby7lUbw"},
    {"order": 120, "topic": "2-D Dynamic Programming", "title": "Regular Expression Matching", "titleSlug": "regular-expression-matching", "difficulty": "Hard", "videoSolution": "https://www.youtube.com/watch?v=HAA8mgxlov8"},
    {"order": 121, "topic": "Greedy", "title": "Maximum Subarray", "titleSlug": "maximum-subarray", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=5WZl3MMT0Eg"},
    {"order": 122, "topic": "Greedy", "title": "Jump Game", "titleSlug": "jump-game", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=Yan0cv2cLy8"},
    {"order": 123, "topic": "Greedy", "title": "Jump Game II", "titleSlug": "jump-game-ii", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=dJ7sWiBQ-M0"},
    {"order": 124, "topic": "Greedy", "title": "Gas Station", "titleSlug": "gas-station", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=lJwbPZGo05A"},
    {"order": 125, "topic": "Greedy", "title": "Hand of Straights", "titleSlug": "hand-of-straights", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=1gD3r2H8p5I"},
    {"order": 126, "topic": "Greedy", "title": "Merge Triplets to Form Target Triplet", "titleSlug": "merge-triplets-to-form-target-triplet", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=kShkQLQZ9K4"},
    {"order": 127, "topic": "Greedy", "title": "Partition Labels", "titleSlug": "partition-labels", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=B7m82zQkr2I"},
    {"order": 128, "topic": "Greedy", "title": "Valid Parenthesis String", "titleSlug": "valid-parenthesis-string", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=QhPdNS143fE"},
    {"order": 129, "topic": "Intervals", "title": "Insert Interval", "titleSlug": "insert-interval", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=A8NUOmlwOlM"},
    {"order": 130, "topic": "Intervals", "title": "Merge Intervals", "titleSlug": "merge-intervals", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=44H3cEC2fFM"},
    {"order": 131, "topic": "Intervals", "title": "Non-overlapping Intervals", "titleSlug": "non-overlapping-intervals", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=nONCGxWoUfM"},
    {"order": 132, "topic": "Intervals", "title": "Meeting Rooms", "titleSlug": "meeting-rooms", "difficulty": "Easy", "videoSolution": "https://www.youtube.com/watch?v=i2bBG7CaVok"},
    {"order": 133, "topic": "Intervals", "title": "Meeting Rooms II", "titleSlug": "meeting-rooms-ii", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=FdzJmTCVyJU"},
    {"order": 134, "topic": "Intervals", "title": "Minimum Interval to Include Each Query", "titleSlug": "minimum-interval-to-include-each-query", "difficulty": "Hard", "videoSolution": "https://www.youtube.com/watch?v=5hQ5WWW5awQ"},
    {"order": 135, "topic": "Math & Geometry", "title": "Rotate Image", "titleSlug": "rotate-image", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=fMSJSS7eO1w"},
    {"order": 136, "topic": "Math & Geometry", "title": "Spiral Matrix", "titleSlug": "spiral-matrix", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=3joo9yAZVh8"},
    {"order": 137, "topic": "Math & Geometry", "title": "Set Matrix Zeroes", "titleSlug": "set-matrix-zeroes", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=T41rL0L3Pnw"},
    {"order": 138, "topic": "Math & Geometry", "title": "Happy Number", "titleSlug": "happy-number", "difficulty": "Easy", "videoSolution": "https://www.youtube.com/watch?v=jB-gALgYgo8"},
    {"order": 139, "topic": "Math & Geometry", "title": "Plus One", "titleSlug": "plus-one", "difficulty": "Easy", "videoSolution": "https://www.youtube.com/watch?v=maN3Y-S-yos"},
    {"order": 140, "topic": "Math & Geometry", "title": "Pow(x, n)", "titleSlug": "powx-n", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=g9YQyYi4IQQ"},
    {"order": 141, "topic": "Math & Geometry", "title": "Multiply Strings", "titleSlug": "multiply-strings", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=1vZ28M-6_K4"},
    {"order": 142, "topic": "Math & Geometry", "title": "Detect Squares", "titleSlug": "detect-squares", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=bahebearrDc"},
    {"order": 143, "topic": "Bit Manipulation", "title": "Single Number", "titleSlug": "single-number", "difficulty": "Easy", "videoSolution": "https://www.youtube.com/watch?v=qMPX1AOa83k"},
    {"order": 144, "topic": "Bit Manipulation", "title": "Number of 1 Bits", "titleSlug": "number-of-1-bits", "difficulty": "Easy", "videoSolution": "https://www.youtube.com/watch?v=5Km3ut2dgNU"},
    {"order": 145, "topic": "Bit Manipulation", "title": "Counting Bits", "titleSlug": "counting-bits", "difficulty": "Easy", "videoSolution": "https://www.youtube.com/watch?v=RyBM56RIWrM"},
    {"order": 146, "topic": "Bit Manipulation", "title": "Reverse Bits", "titleSlug": "reverse-bits", "difficulty": "Easy", "videoSolution": "https://www.youtube.com/watch?v=UcoN6UjAI64"},
    {"order": 147, "topic": "Bit Manipulation", "title": "Missing Number", "titleSlug": "missing-number", "difficulty": "Easy", "videoSolution": "https://www.youtube.com/watch?v=WnPLSRvYvyA"},
    {"order": 148, "topic": "Bit Manipulation", "title": "Sum of Two Integers", "titleSlug": "sum-of-two-integers", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=gV-3O1EEgJA"},
    {"order": 149, "topic": "Bit Manipulation", "title": "Reverse Integer", "titleSlug": "reverse-integer", "difficulty": "Medium", "videoSolution": "https://www.youtube.com/watch?v=Hagj_gtzPuM"},
]
# In app/services/firebase_service.py
# ... (keep all the existing functions) ...

# --- NEW Functions for Friend Request System ---

def create_friend_request(from_user, to_user):
    """Creates a new friend request document in the 'friend_requests' collection."""
    db = _get_db()
    # Check if a request already exists to prevent spam
    existing_request_query = db.collection('friend_requests').where(
        filter=FieldFilter('from_user', '==', from_user)
    ).where(
        filter=FieldFilter('to_user', '==', to_user)
    ).limit(1)
    
    if len(list(existing_request_query.stream())) > 0:
        return "Request already sent."

    request_data = {
        'from_user': from_user,
        'to_user': to_user,
        'status': 'pending',
        'timestamp': firestore.SERVER_TIMESTAMP
    }
    db.collection('friend_requests').add(request_data)
    return "Request sent successfully."

def get_pending_requests(username):
    """Fetches all pending friend requests for a given user."""
    db = _get_db()
    requests_ref = db.collection('friend_requests').where(
        filter=FieldFilter('to_user', '==', username)
    ).where(
        filter=FieldFilter('status', '==', 'pending')
    ).order_by('timestamp', direction='DESCENDING')
    
    requests = []
    for doc in requests_ref.stream():
        req_data = doc.to_dict()
        req_data['id'] = doc.id
        requests.append(req_data)
    return requests

def accept_friend_request(request_id):
    """Accepts a friend request, adds friends to both users, and deletes the request."""
    db = _get_db()
    request_ref = db.collection('friend_requests').document(request_id)
    
    # Use a transaction to ensure all operations succeed or none do
    @firestore.transactional
    def update_in_transaction(transaction, request_ref):
        request_snapshot = request_ref.get(transaction=transaction)
        if not request_snapshot.exists:
            raise Exception("Request does not exist.")
            
        request_data = request_snapshot.to_dict()
        from_user = request_data['from_user']
        to_user = request_data['to_user']
        
        # Add each user to the other's friend list
        from_user_ref = db.collection('users').document(from_user)
        to_user_ref = db.collection('users').document(to_user)
        
        transaction.update(from_user_ref, {'friends': firestore.ArrayUnion([to_user])})
        transaction.update(to_user_ref, {'friends': firestore.ArrayUnion([from_user])})
        
        # Delete the request document now that it's handled
        transaction.delete(request_ref)

    try:
        update_in_transaction(db.transaction(), request_ref)
        return True
    except Exception as e:
        print(f"Error accepting friend request: {e}")
        return False

def reject_friend_request(request_id):
    """Deletes a friend request document."""
    db = _get_db()
    try:
        db.collection('friend_requests').document(request_id).delete()
        return True
    except Exception as e:
        print(f"Error rejecting friend request: {e}")
        return False

def seed_neetcode_plan():
    """
    Automatically populates the `study_plan_questions` collection with the
    NeetCode list. It is idempotent and will not add duplicates.
    """
    db = _get_db()
    collection_ref = db.collection('study_plan_questions')
    
    # Check if the collection is already populated
    if len(list(collection_ref.limit(1).stream())) > 0:
        return "The NeetCode study plan has already been seeded."
        
    try:
        print("Seeding: Populating NeetCode study plan...")
        batch = db.batch()
        for question in NEETCODE_150_QUESTIONS:
            doc_id = f"q{question['order']}"
            doc_ref = collection_ref.document(doc_id)
            batch.set(doc_ref, question)
        
        batch.commit()
        return f"Successfully seeded {len(NEETCODE_150_QUESTIONS)} NeetCode questions!"

    except Exception as e:
        print(f"ERROR during NeetCode seeding: {e}")
        return f"An error occurred during NeetCode seeding: {e}"

def search_study_plan_questions(query_text):
    """
    Searches the list of NeetCode questions for titles that match the query.
    This is a simple in-memory search.
    """
    # NOTE: The NEETCODE_150_QUESTIONS list is defined in this same file.
    if not query_text:
        return []
    
    query_lower = query_text.lower()
    results = []
    for question in NEETCODE_150_QUESTIONS:
        if query_lower in question['title'].lower():
            results.append({
                'title': question['title'],
                'titleSlug': question['titleSlug']
            })
    # Return a maximum of 5 results to keep the dropdown clean
    return results[:5]
