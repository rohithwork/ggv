import json
import pickle
import numpy as np
import faiss
import cohere
from sentence_transformers import SentenceTransformer
import pinecone
from pinecone import ServerlessSpec, Pinecone 
from datetime import datetime

class RAGSystem:
    def __init__(self, api_key, pinecone_api_key, pinecone_environment, index_name):
        # Initialize Cohere client
        self.api_key = api_key
        self.co = cohere.ClientV2(api_key=self.api_key)
        
        # Initialize Pinecone client
        self.pc = Pinecone(api_key=pinecone_api_key)
        self.index_name = index_name
        self.pinecone_environment = pinecone_environment
        
        # Connect to the specified Pinecone index
        try:
            self.index = self.pc.Index(self.index_name)
        except Exception as e:
            raise ValueError(f"Failed to connect to Pinecone index '{index_name}': {str(e)}")
        
        # Initialize embedding model
        self.embedding_model = SentenceTransformer("all-mpnet-base-v2")
        
        # Initialize conversation memory
        self.conversation_summary = ""
        
    def retrieve_documents(self, query, chat_history=None):
        """
        Retrieve relevant documents from Pinecone based on the query and conversation context
        """
        # Create a hybrid query that incorporates conversation context
        hybrid_query = self._create_hybrid_query(query, chat_history)
    
        # Encode the hybrid query
        query_embedding = self.embedding_model.encode(hybrid_query).astype("float32").tolist()
    
        # Query Pinecone for similar documents
        results = self.index.query(
            vector=query_embedding,
            top_k=8,  # Retrieve top 8 candidates
            include_metadata=True
        )
    
        initial_results = []
        for match in results['matches']:
            text = match['metadata'].get('text', "")
            metadata = match['metadata']
            initial_results.append({
                "text": text,
                "metadata": metadata,
                "initial_score": match['score']
            })
    
        candidate_texts = [doc["text"] for doc in initial_results]
        if candidate_texts:
            try:
                # Use the original query for reranking but with context awareness
                context_aware_query = f"{query} (In the context of: {self._extract_key_topics(chat_history)})"

                rerank_response = self.co.rerank(
                    query=context_aware_query,
                    documents=candidate_texts,
                    top_n=min(8, len(candidate_texts)),
                    model="rerank-english-v3.0"
                )

                reranked_results = []
                for res in rerank_response.results:
                    doc = initial_results[res.index]
                    doc["rerank_score"] = res.relevance_score
                    reranked_results.append(doc)
            
                reranked_results = sorted(reranked_results, key=lambda x: x["rerank_score"], reverse=True)
                return reranked_results[:5]  # Return top 5 after reranking
            except Exception as e:
                print(f"Reranking error: {e}")
                return initial_results[:5]
    
        return []
    
    def generate_response_stream(self, user_message, chat_history=None):
        # Retrieve relevant documents with improved context
        retrieved_docs = self.retrieve_documents(user_message, chat_history)
        
        # If no documents found, return a response indicating lack of context
        if not retrieved_docs:
            def no_context_generator():
                yield "I apologize, but I cannot find relevant information to answer this query based on the available context. Could you please rephrase or provide more specific details?"
            return no_context_generator(), []
        
        context = "\n\n".join([doc["text"] for doc in retrieved_docs])
        
        # Prepare a response generation prompt that enforces strict context adherence
        response_generation_prompt = f"""
## Strict Context-Based Response Guidelines
1. ONLY use information from the following retrieved context:
{context}

2. If the query CANNOT be fully answered using ONLY the provided context:
   - Clearly state what information is missing
   - Explain that a complete answer requires additional context
   - Do NOT make up or invent any information

3. Your response must:
   - Directly address the user's query
   - Quote or directly reference the source text
   - Be transparent about the limitations of the available context

## User Query
{user_message}

## Response Instructions
Provide a response that is:
- 100% based on the retrieved context
- Clear and concise
- Explicitly sourced from the given documents
"""
        
        try:
            # Generate response using Cohere's chat API with strict context constraints
            response = self.co.chat(
                model="command-r-plus",
                message=response_generation_prompt,
                temperature=0.1,  # Very low temperature to reduce creativity
                max_tokens=3000,
            )
            
            # Create a generator to simulate streaming
            def response_generator():
                yield response.text if hasattr(response, 'text') else "Unable to generate a response."
            
            # Update conversation memory
            self._update_conversation_memory(user_message, chat_history)
            
            return response_generator(), retrieved_docs
        
        except Exception as e:
            print(f"Error generating response: {e}")
            
            # Return an error generator
            def error_generator():
                yield f"Error generating response: Unable to process the query. {str(e)}"
            
            return error_generator(), []

    # All other methods remain the same as in the original implementation
    # ... (include all other methods from the original class)
    
    def _create_hybrid_query(self, current_query, chat_history=None):
        """
        Create a hybrid query that combines the current query with conversation context
        """
        if not chat_history or len(chat_history) == 0:
            return current_query
        
        # Extract recent user queries (up to 3 most recent)
        recent_queries = []
        user_query_count = 0
        
        for entry in reversed(chat_history):
            is_user = entry[1]
            message_text = entry[2]
            
            if is_user:
                # Only include user messages
                recent_queries.append(message_text)
                user_query_count += 1
                
                if user_query_count >= 3:
                    break
        
        # Reverse back to chronological order
        recent_queries.reverse()
        
        # Extract key topics from the conversation
        conversation_context = self._extract_key_topics(chat_history)
        
        # Combine current query with conversation context
        if recent_queries and conversation_context:
            # Return a query that includes both recent questions and key topics
            return f"{current_query} {' '.join(recent_queries)} {conversation_context}"
        elif recent_queries:
            return f"{current_query} {' '.join(recent_queries)}"
        else:
            return current_query

    def _extract_key_topics(self, chat_history):
        """
        Extract key topics from the conversation history
        """
        if not chat_history or len(chat_history) == 0:
            return ""
            
        # If we have too many messages, use Cohere to summarize key topics
        if len(chat_history) > 5:
            try:
                # Create a conversation transcript
                transcript = "\n".join([f"{'User' if entry[1] else 'Assistant'}: {entry[2]}" for entry in chat_history[-15:]])
                
                # Get key topics using Cohere's summarize endpoint
                response = self.co.summarize(
                    text=transcript,
                    model="command",
                    length="short",
                    format="bullets",
                    extractiveness="high",
                    temperature=0.1,
                )
                
                # Return the summary as key topics
                return response.summary if hasattr(response, 'summary') else ""
                
            except Exception as e:
                print(f"Error extracting key topics: {e}")
                # Fallback to basic extraction
                pass
        
        # Basic extraction - just concatenate the last few user queries
        user_queries = [entry[2] for entry in chat_history if entry[1]]
        return " ".join(user_queries[-3:]) if user_queries else ""
    
    def generate_response_stream(self, user_message, chat_history=None):
        # Retrieve relevant documents with improved context
        retrieved_docs = self.retrieve_documents(user_message, chat_history)
        context = "\n\n".join([doc["text"] for doc in retrieved_docs])
        
        # Construct messages array for the LLM with dynamic prompt engineering
        messages = self._prepare_messages_with_memory(user_message, chat_history, context)
        
        try:
            # Generate streaming response with proper memory management
            stream_response = self.co.chat_stream(
                model="command-r-plus",
                messages=messages,
                temperature=0.7,
                max_tokens=3000,
            )
            
            # Update conversation memory after generating a response
            self._update_conversation_memory(user_message, chat_history)
            
            return stream_response, retrieved_docs
        except Exception as e:
            print(f"Error generating response: {e}")
            # Return an error generator
            def error_generator():
                yield "Error generating response. Please try again."
            return error_generator(), []
    
    def _analyze_query_type(self, user_message, chat_history):
        """
        Analyze the user's query to determine the appropriate response strategy
        """
        # Convert to lowercase for easier pattern matching
        message = user_message.lower()
        
        # Check for follow-up indicators
        follow_up_phrases = ["what about", "how about", "and", "also", "then", "so", "therefore", 
                            "but what if", "why", "could you", "additionally", "furthermore"]
        
        is_short_query = len(message.split()) < 5
        has_pronouns = any(word in message.split() for word in ["it", "they", "them", "this", "that", "these", "those"])
        
        # Stronger follow-up detection by combining multiple signals
        if chat_history and (
            any(phrase in message for phrase in follow_up_phrases) or 
            (is_short_query and has_pronouns)
        ):
            return "follow_up"
        
        # Check for comparative analysis requests
        comparative_phrases = ["versus", "compare", "comparison", "difference", "vs", "better", 
                              "advantages", "disadvantages", "pros and cons", "relative to"]
        
        if any(phrase in message for phrase in comparative_phrases):
            return "comparative"
        
        # Check for analysis requests
        analytical_phrases = ["analyze", "analysis", "evaluate", "assessment", "outlook", 
                             "perspective", "implications", "impact", "effects", "strategy", 
                             "recommend", "opportunity", "risk", "potential", "forecast"]
        
        if any(phrase in message for phrase in analytical_phrases):
            return "analytical"
        
        # Check for factual information requests
        factual_phrases = ["what is", "how much", "when did", "where is", "who is", 
                          "data", "statistics", "numbers", "percentage", "rate", "figure", 
                          "amount", "total", "count", "value"]
        
        if any(phrase in message for phrase in factual_phrases):
            return "factual"
        
        # Check for market overview requests
        market_phrases = ["market", "industry", "sector", "overview", "landscape", 
                         "trends", "growth", "expansion", "decline", "outlook"]
                         
        if any(phrase in message for phrase in market_phrases) and any(word in message for word in ["overview", "summary", "landscape", "state of"]):
            return "market_overview"
        
        # Check for specific company analysis
        if ("company" in message or any(company_indicator in message for company_indicator in [" inc", " corp", " ltd", " llc"])) and len(message.split()) < 15:
            return "company_profile"
        
        # Default to general comprehensive approach
        return "general"
    
    def _prepare_messages_with_memory(self, user_message, chat_history, context):
        """
        Prepare messages for the LLM with dynamic prompt engineering based on the query type
        """
        # Base system message with core capabilities
        base_system_message = """
## Role and Expertise
You are the Chief Investment Analyst AI for Golden Gate Ventures, a premier investment management firm. Your expertise spans venture capital, private equity, public markets, and emerging investment opportunities.
"""

        # Analyze the user's query to determine the appropriate prompt strategy
        query_type = self._analyze_query_type(user_message, chat_history)
    
        # Add specialized instructions based on query type
        if query_type == "factual":
            system_message = base_system_message + """
## Query Context: Factual Information Request
For this factual query, prioritize:
- Precise data points, figures, and metrics from the context
- Clear citation of sources where available
- Concise, direct answers without unnecessary elaboration
- Structured presentation of numerical data when relevant
"""
        elif query_type == "analytical":
            system_message = base_system_message + """
## Query Context: Analytical Request
For this analytical query, prioritize:
- Thorough examination of multiple perspectives and factors
- Connecting data points to reveal meaningful patterns and insights
- Balanced assessment of risks and opportunities
- Progressive disclosure of complex ideas with clear logical flow
- Strategic implications and actionable conclusions
"""
        elif query_type == "follow_up":
            system_message = base_system_message + """
## Query Context: Follow-up Question
This appears to be a follow-up to our earlier discussion. Prioritize:
- Direct connection to previously discussed topics
- Contextual continuity with our conversation history
- Progressive building on established concepts
- Addressing any implicit assumptions from earlier exchanges
"""
        elif query_type == "comparative":
            system_message = base_system_message + """
## Query Context: Comparative Analysis Request
For this comparative query, prioritize:
- Side-by-side analysis of the compared elements
- Clear evaluation criteria and metrics
- Balanced assessment of strengths and weaknesses
- Visual organization to highlight key differences
- Contextual factors that influence the comparison
"""
        elif query_type == "market_overview":
            system_message = base_system_message + """
## Query Context: Market Overview Request
For this market overview query, prioritize:
- High-level industry trends and market dynamics
- Key market segments and their relative sizes
- Growth rates and market trajectory
- Major players and competitive landscape
- Macro factors influencing the market
- Visual representation of market structure when helpful
"""
        elif query_type == "company_profile":
            system_message = base_system_message + """
## Query Context: Company Analysis Request
For this company-specific query, prioritize:
- Company background and core business model
- Key financial metrics and performance indicators
- Market position and competitive advantages
- Growth strategy and recent developments
- Risk factors and challenges
- Management team highlights if available
"""
        else:  # Default to comprehensive approach
            system_message = base_system_message + """
## Query Context: Investment Intelligence Request
Deliver investment intelligence that is:
- Thoroughly researched (based exclusively on the provided context)
- Precisely articulated (with specific metrics, figures, and dates)
- Professionally presented (with clear structure)
- Actionable for investment decision-making
"""
    
    # Add universal capabilities section that applies to all responses
        system_message += """
## Universal Response Requirements
1. Extract relevant information from the context that directly addresses the query
2. Include specific metrics and figures when available
3. Only use information contained in the provided context material
4. Begin with a concise executive summary or key takeaway
5. Maintain awareness of our entire conversation history

## Numeric Presentation Guidelines
- Always format numeric values for maximum readability
- Use comma separators for thousands (e.g., 1,234,567)
- Round decimal values to 2 decimal places when appropriate
- For very large numbers, use millions/billions notation (e.g., 3.5M, 2.1B)
- Clearly distinguish between percentages, absolute numbers, and monetary values
- Use consistent decimal precision across related numeric values
- When presenting financial data, use appropriate decimal places:
  * Percentages: 2 decimal places (e.g., 12.45%)
  * Currency: 2 decimal places (e.g., $1,234.56)
  * Large numbers: Millions/Billions notation
- Ensure numeric values are easily readable and comprehensible
"""

        # Start with the system message
        messages = [{"role": "system", "content": system_message}]
    
        # Add conversation memory if we have it
        if self.conversation_summary:
            messages.append({
                "role": "system", 
                "content": f"## Conversation Memory\nKey topics and information from previous exchanges:\n\n{self.conversation_summary}"
            })
    
        # Select most relevant messages from chat history
        selected_messages = self._select_relevant_messages(user_message, chat_history)
    
        # Add selected messages to provide continuity
        for entry in selected_messages:
            role = "user" if entry[1] else "assistant"
            messages.append({"role": role, "content": entry[2]})
    
        # Dynamically format the context based on source material types and query
        context_message = self._format_context_for_query(user_message, context, query_type)
    
        # Add the current question with context
        messages.append({"role": "user", "content": context_message})
    
        return messages
    
    def _format_context_for_query(self, user_message, context, query_type):
        """
        Dynamically format the context based on the query type and available information
        """
        # Base context formatting
        context_message = "## Investment Intelligence Briefing\n\n"
        
        # Add appropriate header based on query type
        if query_type == "factual":
            context_message += "### Factual Information Sources\n"
        elif query_type == "analytical":
            context_message += "### Analysis Source Material\n"
        elif query_type == "comparative":
            context_message += "### Comparative Analysis Sources\n"
        elif query_type == "follow_up":
            context_message += "### Additional Context for Follow-up\n"
        elif query_type == "market_overview":
            context_message += "### Market Research Sources\n"
        elif query_type == "company_profile":
            context_message += "### Company Information Sources\n"
        else:
            context_message += "### Source Material\n"
        
        # Add the context with better delineation between potentially different sources
        formatted_context = self._enhance_context_presentation(context, query_type)
        context_message += f"{formatted_context}\n\n"
        
        # Add user query with appropriate framing
        if query_type == "follow_up":
            context_message += "### Follow-up Query\n"
            context_message += f"{user_message}\n\n"
            context_message += "Remember to connect this to our previous discussion points and answer in context of our conversation history.\n"
        elif query_type == "comparative":
            context_message += "### Comparative Analysis Request\n"
            context_message += f"{user_message}\n\n"
            context_message += "Present a balanced and structured comparison of the elements mentioned.\n"
        elif query_type == "analytical":
            context_message += "### Analysis Request\n"
            context_message += f"{user_message}\n\n"
            context_message += "Provide strategic insights and connect different data points into a cohesive analysis.\n"
        elif query_type == "factual":
            context_message += "### Factual Query\n"
            context_message += f"{user_message}\n\n"
            context_message += "Provide precise information with specific figures and metrics where available.\n"
        elif query_type == "market_overview":
            context_message += "### Market Overview Request\n"
            context_message += f"{user_message}\n\n"
            context_message += "Provide a comprehensive view of market dynamics, trends, and competitive landscape.\n"
        elif query_type == "company_profile":
            context_message += "### Company Analysis Request\n"
            context_message += f"{user_message}\n\n"
            context_message += "Provide a concise company profile with key metrics and performance indicators.\n"
        else:
            context_message += "### Current Query\n"
            context_message += f"{user_message}\n\n"
        
        return context_message
    
    def _enhance_context_presentation(self, context, query_type):
        """
        Enhance the presentation of context based on query type
        """
        # Split the context into chunks (assuming each document is separated by newlines)
        chunks = context.split("\n\n")
        
        # For short contexts or follow-ups, keep the original format
        if len(chunks) <= 1 or query_type == "follow_up":
            return context
            
        # For most query types, add source delineation
        formatted_chunks = []
        for i, chunk in enumerate(chunks):
            if chunk.strip():  # Skip empty chunks
                formatted_chunks.append(f"SOURCE {i+1}:\n{chunk.strip()}")
        
        return "\n\n".join(formatted_chunks)
    
    def _select_relevant_messages(self, user_message, chat_history):
        """
        Intelligently select the most relevant messages from chat history
        """
        if not chat_history or len(chat_history) <= 6:
            # If we have 6 or fewer messages, include all of them
            return chat_history or []
        
        # For longer conversations, we need to be selective
        selected_messages = []
        
        # Always include the most recent exchanges (last 3 turns)
        selected_messages.extend(chat_history[-6:])
        
        # If we have a longer history, try to find related earlier messages
        if len(chat_history) > 6:
            try:
                # Create embeddings for all messages and the current query
                all_messages = [msg[2] for msg in chat_history[:-6]]  # Skip the most recent 6 we already included
                
                if not all_messages:
                    return selected_messages
                
                all_embeddings = self.embedding_model.encode(all_messages, convert_to_numpy=True)
                query_embedding = self.embedding_model.encode(user_message, convert_to_numpy=True)
                
                # Calculate similarity
                similarities = np.dot(all_embeddings, query_embedding) / (
                    np.linalg.norm(all_embeddings, axis=1) * np.linalg.norm(query_embedding)
                )
                
                # Get indices of most similar messages (up to 4 additional messages)
                top_indices = np.argsort(similarities)[-4:][::-1]
                
                # Only include messages with similarity above threshold
                threshold = 0.3
                relevant_indices = [idx for idx in top_indices if similarities[idx] > threshold]
                
                # Add selected relevant messages from earlier in the conversation
                for idx in sorted(relevant_indices):  # Sort to maintain chronological order
                    selected_messages.append(chat_history[idx])
                
            except Exception as e:
                print(f"Error selecting relevant messages: {e}")
                # Fallback to including first and last messages
                if len(chat_history) > 12:
                    selected_messages.extend(chat_history[:2])  # First 2 messages for context
        
        # Sort all selected messages by their original order
        message_indices = {msg[0]: i for i, msg in enumerate(chat_history)}
        selected_messages.sort(key=lambda msg: message_indices.get(msg[0], 0))
        
        return selected_messages
    
    def _update_conversation_memory(self, user_message, chat_history):
        """
        Update the conversation memory after each exchange
        """
        if not chat_history or len(chat_history) < 4:
            # Not enough history to create a meaningful summary
            return
            
        try:
            # If we have a substantial conversation, use Cohere to maintain a running summary
            # Create a transcript of the most recent part of the conversation
            recent_exchanges = chat_history[-10:] if len(chat_history) >= 10 else chat_history
            transcript = "\n".join([f"{'User' if entry[1] else 'Assistant'}: {entry[2]}" for entry in recent_exchanges])
            transcript += f"\nUser: {user_message}"
            
            # If we already have a conversation summary, include it for continuity
            if self.conversation_summary:
                prompt = f"""
Previous conversation summary:
{self.conversation_summary}

New conversation segment:
{transcript}

Create an updated summary of the entire conversation that:
1. Integrates new information with the previous summary
2. Preserves key topics, entities, and data points from the entire conversation
3. Is organized by topic rather than chronologically
4. Focuses on information that might be referenced in follow-up questions
5. Is concise but comprehensive
"""
            else:
                prompt = f"""
Based on this conversation:
{transcript}

Create a summary that:
1. Identifies key topics, entities, and data points discussed
2. Is organized by topic rather than chronologically
3. Focuses on information that might be referenced in follow-up questions
4. Is concise but comprehensive
"""
            
            # Generate a new conversation summary
            response = self.co.chat(
                model="command",
                message=prompt,
                temperature=0.2,
                max_tokens=500
            )
            
            if hasattr(response, 'text'):
                self.conversation_summary = response.text
            
        except Exception as e:
            print(f"Error updating conversation memory: {e}")
            # If summarization fails, create a simple summary
            if len(chat_history) > 8:
                user_queries = [entry[2] for entry in chat_history if entry[1]]
                self.conversation_summary = "Topics discussed: " + " | ".join(user_queries[-5:])

    def generate_chat_title(self, message_content):
        """
        Generate a descriptive title for a conversation based on its content
        """
        if not message_content or len(message_content.strip()) < 5:
            return "New Chat"
    
        try:
            # Create a simple, direct prompt for the title generation
            prompt = f"Generate a short, specific 3-5 word title for a chat about: {message_content[:250]}"
        
            # Use the Cohere API to generate a title
            response = self.co.chat(
                model="command",
                message=prompt,
                temperature=0.3,  # Lower temperature for more consistent results
                max_tokens=15,    # Limit tokens to enforce brevity
            )

            # Extract and clean the title
            if hasattr(response, 'text'):
                # Clean up the title
                title = response.text.strip()
            
                # Remove quotes and other unwanted characters
                title = title.strip('"\'').strip()
            
                # Remove common prefixes that might appear
                prefixes = ["Title:", "Chat title:", "Conversation title:", "Topic:"]
                for prefix in prefixes:
                    if title.lower().startswith(prefix.lower()):
                        title = title[len(prefix):].strip()
            
                # Enforce length constraints
                if len(title) > 40:
                    # Find a good breaking point if title is too long
                    breaking_point = title[:40].rfind(' ')
                    if breaking_point > 10:  # Make sure we have a reasonable title length
                        title = title[:breaking_point] + "..."
                    else:
                        title = title[:37] + "..."
            
                # Fall back if the title is empty or too short
                if not title or len(title) < 3:
                    # Extract key topics from the message as a fallback
                    key_words = [word for word in message_content.split() 
                                 if len(word) > 3 and word.lower() not in 
                                 ['what', 'when', 'where', 'which', 'tell', 'about', 'from', 'that', 'this', 'with']]
                    if key_words:
                        # Use the first few significant words
                        title = ' '.join(key_words[:3]).title()
                    else:
                        title = "Discussion " + datetime.now().strftime("%b %d")
            
                return title
        
            return "Chat " + datetime.now().strftime("%b %d, %H:%M")
    
        except Exception as e:
            print(f"Error generating chat title: {e}")
            # Generate a timestamp-based title as a fallback
            return "Chat " + datetime.now().strftime("%b %d, %H:%M")
