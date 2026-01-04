"""
Fast Intent Detector - Quick LLM-based intent detection
Detects conversational queries BEFORE loading context to save time
Uses lightweight LLM call without context
"""
import logging
import json
from typing import Optional, Dict, Any
from ..schemas import ChatLanguage

logger = logging.getLogger(__name__)


class FastIntentDetector:
    """
    Fast LLM-based intent detector for conversational queries.
    Uses lightweight LLM call without context to quickly detect intent.
    """
    
    async def detect_and_respond(
        self,
        llm_gateway,
        question: str,
        language: ChatLanguage,
        model_id: int,
        conversation_history: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        Fast intent detection with immediate response generation for conversational queries.
        
        Args:
            llm_gateway: LLM gateway instance
            question: User question
            language: Language of the question
            model_id: LLM model ID
            conversation_history: Optional conversation history
            
        Returns:
            Dict with keys:
            - is_conversational: bool
            - intent: str (if detected)
            - response: str (if conversational, ready to return)
            - confidence: float
        """
        import time
        start_time = time.time()
        
        # Build lightweight prompt for fast intent detection + response generation
        if language == ChatLanguage.PERSIAN:
            prompt = f"""شما یک دستیار هوشمند و دوستانه هستید. سوال کاربر را تحلیل کنید و اگر مکالمه عادی است، همانجا پاسخ دهید.

سوال کاربر: {question}

{self._format_history(conversation_history) if conversation_history else ""}

وظیفه:
- اگر سوال یک مکالمه عادی است (سلام، تشکر، کمک، سوال درباره خودتان، و غیره):
  پاسخ دهید: {{"intent": "CONVERSATIONAL", "response": "یک پاسخ دوستانه و مفید به فارسی (حداکثر 2 جمله)", "confidence": 0.9}}
  
- اگر سوال درباره داده/دیتابیس/جستجو است (قیمت، تعداد، لیست، نمایش، و غیره):
  پاسخ دهید: {{"intent": "DATA_QUERY", "confidence": 0.9}}

مثال‌های مکالمه عادی: "سلام"، "ممنون"، "کمک می‌خواهم"، "چی می‌تونی بکنی"، "خداحافظ"
مثال‌های سوال داده: "قیمت قیر چقدر است"، "چند محصول داریم"، "لیست محصولات را نشان بده"

فقط JSON برگردانید، بدون توضیح اضافه."""
        else:
            prompt = f"""You are a friendly and intelligent assistant. Analyze the user's question and if it's a normal conversation, respond immediately.

User question: {question}

{self._format_history(conversation_history) if conversation_history else ""}

Task:
- If the question is a normal conversation (greeting, thanks, help, question about yourself, etc.):
  Respond: {{"intent": "CONVERSATIONAL", "response": "A friendly and helpful response in English (maximum 2 sentences)", "confidence": 0.9}}
  
- If the question is about data/database/search (price, count, list, show, etc.):
  Respond: {{"intent": "DATA_QUERY", "confidence": 0.9}}

Examples of conversation: "hi", "thanks", "help", "what can you do", "goodbye"
Examples of data query: "what is the price of X", "how many products", "show me the list"

Return ONLY JSON, no additional explanation."""
        
        try:
            logger.info(f"⚡ FAST_INTENT_START | Question: '{question[:50]}...' | Language: {language}")
            
            # Single lightweight LLM call
            llm_response = await llm_gateway.call_llm(
                model_id=model_id,
                prompt=prompt,
                temperature=0.7,  # Slightly higher for conversational responses
                max_tokens=200  # Limit tokens for speed
            )
            
            detection_time = int((time.time() - start_time) * 1000)
            
            if not llm_response.success:
                logger.warning(f"⚠️ FAST_INTENT_LLM_FAILED | Time: {detection_time}ms | Error: {llm_response.error_message}")
                # Retry with simpler prompt - let model decide
                logger.info(f"🔄 FAST_INTENT_RETRY | Retrying with simpler prompt after LLM failure")
                return await self._retry_with_simple_prompt(
                    llm_gateway, question, language, model_id, conversation_history, detection_time
                )
            
            # Parse response
            try:
                from ..utils.json_safety import safe_json_parse
                result = safe_json_parse(llm_response.raw_text)
                
                intent = result.get("intent", "").upper()
                is_conversational = intent == "CONVERSATIONAL"
                response = result.get("response", "") if is_conversational else None
                confidence = result.get("confidence", 0.5)
                
                logger.info(
                    f"✅ FAST_INTENT_COMPLETE | Intent: {intent} | "
                    f"Conversational: {is_conversational} | "
                    f"Confidence: {confidence:.2f} | "
                    f"Time: {detection_time}ms"
                )
                
                return {
                    "is_conversational": is_conversational,
                    "intent": intent,
                    "response": response,
                    "confidence": confidence,
                    "detection_time_ms": detection_time
                }
                
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                logger.warning(f"⚠️ FAST_INTENT_PARSE_ERROR | Time: {detection_time}ms | Error: {e} | Response: {llm_response.raw_text[:100]}")
                
                # Fallback: Ask LLM again with simpler prompt (مدل تصمیم می‌گیرد)
                logger.info(f"🔄 FAST_INTENT_RETRY | Retrying with simpler prompt - Let model decide")
                return await self._retry_with_simple_prompt(
                    llm_gateway, question, language, model_id, conversation_history, detection_time
                )
                
        except Exception as e:
            detection_time = int((time.time() - start_time) * 1000)
            logger.error(f"❌ FAST_INTENT_ERROR | Time: {detection_time}ms | Error: {str(e)}", exc_info=True)
            # Last resort: try one more time with simplest prompt
            logger.info(f"🔄 FAST_INTENT_LAST_RESORT | Trying last resort LLM call")
            return await self._last_resort_llm_response(
                llm_gateway, question, language, model_id, conversation_history, detection_time
            )
    
    async def _retry_with_simple_prompt(
        self,
        llm_gateway,
        question: str,
        language: ChatLanguage,
        model_id: int,
        conversation_history: Optional[list] = None,
        previous_time: int = 0
    ) -> Dict[str, Any]:
        """Retry with simpler prompt if first attempt failed"""
        if language == ChatLanguage.PERSIAN:
            prompt = f"""سوال: {question}

آیا این یک مکالمه عادی است (سلام، تشکر، کمک) یا سوال درباره داده؟

اگر مکالمه عادی: {{"intent": "CONVERSATIONAL", "response": "پاسخ دوستانه", "confidence": 0.8}}
اگر سوال داده: {{"intent": "DATA_QUERY", "confidence": 0.8}}

فقط JSON:"""
        else:
            prompt = f"""Question: {question}

Is this a normal conversation (greeting, thanks, help) or a data question?

If conversation: {{"intent": "CONVERSATIONAL", "response": "Friendly response", "confidence": 0.8}}
If data question: {{"intent": "DATA_QUERY", "confidence": 0.8}}

JSON only:"""
        
        try:
            llm_response = await llm_gateway.call_llm(
                model_id=model_id,
                prompt=prompt,
                temperature=0.5,
                max_tokens=150
            )
            
            if llm_response.success:
                from ..utils.json_safety import safe_json_parse
                result = safe_json_parse(llm_response.raw_text)
                intent = result.get("intent", "").upper()
                is_conversational = intent == "CONVERSATIONAL"
                
                return {
                    "is_conversational": is_conversational,
                    "intent": intent,
                    "response": result.get("response", "") if is_conversational else None,
                    "confidence": result.get("confidence", 0.7),
                    "detection_time_ms": previous_time
                }
        except Exception as e:
            logger.error(f"❌ RETRY_PROMPT_ERROR | Error: {str(e)}")
        
        # Last resort: Ask LLM to just respond (no JSON parsing)
        return await self._last_resort_llm_response(
            llm_gateway, question, language, model_id, conversation_history, previous_time
        )
    
    async def _last_resort_llm_response(
        self,
        llm_gateway,
        question: str,
        language: ChatLanguage,
        model_id: int,
        conversation_history: Optional[list] = None,
        previous_time: int = 0
    ) -> Dict[str, Any]:
        """Last resort: Ask LLM to just respond directly"""
        if language == ChatLanguage.PERSIAN:
            prompt = f"""سوال کاربر: {question}

{self._format_history(conversation_history) if conversation_history else ""}

اگر این یک مکالمه عادی است (سلام، تشکر، کمک)، یک پاسخ دوستانه بنویس.
اگر سوال درباره داده است، فقط بنویس: "DATA_QUERY"

پاسخ:"""
        else:
            prompt = f"""User question: {question}

{self._format_history(conversation_history) if conversation_history else ""}

If this is a normal conversation (greeting, thanks, help), write a friendly response.
If it's a data question, just write: "DATA_QUERY"

Response:"""
        
        try:
            llm_response = await llm_gateway.call_llm(
                model_id=model_id,
                prompt=prompt,
                temperature=0.7,
                max_tokens=200
            )
            
            if llm_response.success:
                response_text = llm_response.raw_text.strip()
                is_conversational = "DATA_QUERY" not in response_text.upper()
                
                return {
                    "is_conversational": is_conversational,
                    "intent": "CONVERSATIONAL" if is_conversational else "DATA_QUERY",
                    "response": response_text if is_conversational else None,
                    "confidence": 0.6,  # Lower confidence for last resort
                    "detection_time_ms": previous_time
                }
        except Exception as e:
            logger.error(f"❌ LAST_RESORT_ERROR | Error: {str(e)}")
        
        # If all LLM calls fail, return unknown (let normal pipeline handle it)
        # Model couldn't decide, so we let the full pipeline decide
        logger.warning(f"⚠️ ALL_LLM_ATTEMPTS_FAILED | Letting normal pipeline handle")
        return {
            "is_conversational": False,
            "intent": None,
            "response": None,
            "confidence": 0.0,
            "detection_time_ms": previous_time
        }
    
    async def _generate_quick_response(
        self,
        llm_gateway,
        question: str,
        language: ChatLanguage,
        model_id: int,
        conversation_history: Optional[list] = None
    ) -> str:
        """Generate quick conversational response using LLM only"""
        if language == ChatLanguage.PERSIAN:
            prompt = f"""شما یک دستیار هوشمند و دوستانه هستید. به سوال کاربر پاسخ دهید.

سوال: {question}

{self._format_history(conversation_history) if conversation_history else ""}

پاسخ دوستانه و مفید به فارسی بنویسید (حداکثر 2 جمله):"""
        else:
            prompt = f"""You are a friendly and intelligent assistant. Respond to the user's question.

Question: {question}

{self._format_history(conversation_history) if conversation_history else ""}

Write a friendly and helpful response in English (maximum 2 sentences):"""
        
        try:
            llm_response = await llm_gateway.call_llm(
                model_id=model_id,
                prompt=prompt,
                temperature=0.7,
                max_tokens=150  # Short response
            )
            
            if llm_response.success:
                return llm_response.raw_text.strip()
            else:
                # Try one more time with even simpler prompt
                logger.warning(f"⚠️ QUICK_RESPONSE_FAILED | Retrying with simpler prompt")
                return await self._generate_simple_response(
                    llm_gateway, question, language, model_id
                )
        except Exception as e:
            logger.error(f"❌ QUICK_RESPONSE_ERROR | Error: {str(e)}")
            return await self._generate_simple_response(
                llm_gateway, question, language, model_id
            )
    
    async def _generate_simple_response(
        self,
        llm_gateway,
        question: str,
        language: ChatLanguage,
        model_id: int
    ) -> str:
        """Generate simple response with minimal prompt"""
        if language == ChatLanguage.PERSIAN:
            prompt = f"""سوال: {question}

پاسخ دوستانه و کوتاه به فارسی:"""
        else:
            prompt = f"""Question: {question}

Friendly and short response in English:"""
        
        try:
            llm_response = await llm_gateway.call_llm(
                model_id=model_id,
                prompt=prompt,
                temperature=0.7,
                max_tokens=100
            )
            
            if llm_response.success:
                return llm_response.raw_text.strip()
        except Exception as e:
            logger.error(f"❌ SIMPLE_RESPONSE_ERROR | Error: {str(e)}")
        
        # If all LLM calls fail, try one absolute last attempt with minimal prompt
        logger.warning(f"⚠️ ALL_LLM_CALLS_FAILED | Trying absolute last resort")
        try:
            if language == ChatLanguage.PERSIAN:
                last_prompt = f"سوال: {question}\n\nپاسخ کوتاه:"
            else:
                last_prompt = f"Question: {question}\n\nShort response:"
            
            llm_response = await llm_gateway.call_llm(
                model_id=model_id,
                prompt=last_prompt,
                temperature=0.7,
                max_tokens=50
            )
            
            if llm_response.success:
                return llm_response.raw_text.strip()
        except Exception as e:
            logger.error(f"❌ ABSOLUTE_LAST_RESORT_ERROR | Error: {str(e)}")
        
        # Only if ALL LLM attempts fail, return None to let normal pipeline handle
        logger.error(f"❌ ALL_LLM_ATTEMPTS_FAILED | Returning None - will use normal pipeline")
        return None
    
    def _format_history(self, history: list) -> str:
        """Format conversation history for prompt"""
        if not history:
            return ""
        
        formatted = []
        for msg in history[-3:]:  # Last 3 messages
            question = msg.get("question", "")
            if question:
                formatted.append(f"Previous: {question}")
        
        return "\n".join(formatted) + "\n" if formatted else ""
    

