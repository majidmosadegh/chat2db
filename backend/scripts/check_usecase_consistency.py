#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script to check use case consistency:
- Check if questions and queries match in count
- Check if questions and queries are logically related
- Identify mismatches and inconsistencies
"""

import asyncio
import sys
import json
import io
from pathlib import Path

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from api.db_models import UseCase, get_db_session
from sqlalchemy.ext.asyncio import AsyncSession


def analyze_question_query_match(question: str, query: str) -> dict:
    """Analyze if a question and query are logically related"""
    question_lower = question.lower()
    query_lower = query.lower()
    
    # Extract key terms from question
    question_keywords = set()
    # Common business terms
    business_terms = ['قیمت', 'حجم', 'تعداد', 'میانگین', 'حداکثر', 'حداقل', 'جمع', 'تاریخ', 'شرکت', 'محصول', 'کالا', 'معامله']
    for term in business_terms:
        if term in question_lower:
            question_keywords.add(term)
    
    # Extract SQL keywords from query
    sql_keywords = ['select', 'from', 'where', 'group by', 'order by', 'sum', 'avg', 'count', 'max', 'min']
    query_has_aggregation = any(kw in query_lower for kw in ['sum', 'avg', 'count', 'max', 'min'])
    
    # Check if query seems to answer the question
    match_score = 0
    issues = []
    
    # Check 1: Does query have aggregation when question asks for aggregation?
    if any(term in question_lower for term in ['میانگین', 'حداکثر', 'حداقل', 'جمع', 'تعداد']):
        if not query_has_aggregation:
            issues.append("Question asks for aggregation but query doesn't use aggregation functions")
        else:
            match_score += 1
    
    # Check 2: Does query have WHERE clause when question has filters?
    if any(term in question_lower for term in ['در تاریخ', 'برای', 'که', 'کدام']):
        if 'where' not in query_lower:
            issues.append("Question has filters but query doesn't have WHERE clause")
        else:
            match_score += 1
    
    # Check 3: Does query select relevant columns?
    # This is harder to check automatically, but we can check if query has SELECT
    if 'select' not in query_lower:
        issues.append("Query doesn't have SELECT clause")
    else:
        match_score += 1
    
    return {
        "match_score": match_score,
        "max_score": 3,
        "issues": issues,
        "has_aggregation": query_has_aggregation,
        "has_where": 'where' in query_lower
    }


async def check_all_usecases():
    """Check all use cases for consistency"""
    print("=" * 80)
    print("USE CASE CONSISTENCY CHECKER")
    print("=" * 80)
    print()
    
    async for session in get_db_session():
        try:
            # Get all use cases
            result = await session.execute(select(UseCase).order_by(UseCase.id))
            use_cases = result.scalars().all()
            
            print(f"Found {len(use_cases)} use cases\n")
            
            total_issues = 0
            use_cases_with_issues = []
            
            for uc in use_cases:
                print(f"\n{'='*80}")
                print(f"Use Case ID: {uc.id}")
                print(f"Name: {uc.name}")
                print(f"Business Goal: {uc.business_goal[:100]}..." if len(uc.business_goal) > 100 else f"Business Goal: {uc.business_goal}")
                print(f"{'='*80}")
                
                # Parse JSON fields
                try:
                    example_questions = json.loads(uc.example_questions or "[]")
                except:
                    example_questions = []
                    print(f"  ⚠️  ERROR: Could not parse example_questions")
                
                try:
                    example_queries = json.loads(uc.example_queries or "[]")
                except:
                    example_queries = []
                    print(f"  ⚠️  ERROR: Could not parse example_queries")
                
                # Check counts
                questions_count = len(example_questions) if isinstance(example_questions, list) else 0
                queries_count = len(example_queries) if isinstance(example_queries, list) else 0
                
                print(f"\n  Questions: {questions_count}")
                print(f"  Queries: {queries_count}")
                
                issues = []
                
                # Issue 1: Count mismatch
                if questions_count != queries_count:
                    issues.append(f"❌ COUNT MISMATCH: {questions_count} questions but {queries_count} queries")
                    total_issues += 1
                else:
                    print(f"  ✅ Counts match")
                
                # Issue 2: Empty lists
                if questions_count == 0:
                    issues.append("❌ NO QUESTIONS: example_questions is empty")
                    total_issues += 1
                
                if queries_count == 0:
                    issues.append("❌ NO QUERIES: example_queries is empty")
                    total_issues += 1
                
                # Issue 3: Check each question-query pair
                if questions_count > 0 and queries_count > 0:
                    min_count = min(questions_count, queries_count)
                    print(f"\n  Analyzing {min_count} question-query pairs:")
                    
                    for i in range(min_count):
                        question = example_questions[i] if i < len(example_questions) else None
                        query = example_queries[i] if i < len(example_queries) else None
                        
                        if not question:
                            issues.append(f"  ❌ Pair {i+1}: Question is None or empty")
                            total_issues += 1
                            continue
                        
                        if not query:
                            issues.append(f"  ❌ Pair {i+1}: Query is None or empty")
                            total_issues += 1
                            continue
                        
                        # Analyze match
                        analysis = analyze_question_query_match(question, query)
                        
                        print(f"\n    Pair {i+1}:")
                        print(f"      Question: {question[:80]}..." if len(question) > 80 else f"      Question: {question}")
                        print(f"      Query: {query[:80]}..." if len(query) > 80 else f"      Query: {query}")
                        print(f"      Match Score: {analysis['match_score']}/{analysis['max_score']}")
                        
                        if analysis['issues']:
                            for issue in analysis['issues']:
                                issues.append(f"  ⚠️  Pair {i+1}: {issue}")
                                total_issues += 1
                        
                        # Check if question and query seem related
                        if analysis['match_score'] < 2:
                            issues.append(f"  ⚠️  Pair {i+1}: Question and query may not be well matched (low match score)")
                
                # Issue 4: Check for generic/placeholder questions
                if isinstance(example_questions, list):
                    for i, q in enumerate(example_questions):
                        if q and isinstance(q, str):
                            q_lower = q.lower().strip()
                            # Check for technical prefixes
                            if q_lower.startswith(('query:', 'sql:', 'کوئری:', 'سوال:')):
                                issues.append(f"  ❌ Question {i+1}: Starts with technical prefix (invalid format)")
                                total_issues += 1
                            # Check for generic questions
                            if 'what information can i get' in q_lower or 'what can i get' in q_lower:
                                issues.append(f"  ⚠️  Question {i+1}: Generic placeholder question")
                                total_issues += 1
                
                # Issue 5: Check for placeholder queries
                if isinstance(example_queries, list):
                    for i, q in enumerate(example_queries):
                        if q and isinstance(q, str):
                            q_lower = q.lower().strip()
                            if 'information_schema' in q_lower or 'select * from information_schema' in q_lower:
                                issues.append(f"  ❌ Query {i+1}: Placeholder query (information_schema)")
                                total_issues += 1
                
                # Print all issues
                if issues:
                    print(f"\n  ISSUES FOUND ({len(issues)}):")
                    for issue in issues:
                        print(f"    {issue}")
                    use_cases_with_issues.append({
                        "id": uc.id,
                        "name": uc.name,
                        "issues_count": len(issues),
                        "issues": issues
                    })
                else:
                    print(f"\n  ✅ No issues found!")
            
            # Summary
            print(f"\n\n{'='*80}")
            print("SUMMARY")
            print(f"{'='*80}")
            print(f"Total Use Cases: {len(use_cases)}")
            print(f"Use Cases with Issues: {len(use_cases_with_issues)}")
            print(f"Total Issues Found: {total_issues}")
            
            if use_cases_with_issues:
                print(f"\nUse Cases with Issues:")
                for uc_issue in use_cases_with_issues:
                    print(f"  - ID {uc_issue['id']}: {uc_issue['name']} ({uc_issue['issues_count']} issues)")
            
            break
            
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
            break


if __name__ == "__main__":
    asyncio.run(check_all_usecases())

