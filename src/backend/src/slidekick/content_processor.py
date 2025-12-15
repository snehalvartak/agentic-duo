import logging
from pathlib import Path
from google import genai

import slidekick.config as config

logger = logging.getLogger(__name__)

class ContentProcessor:
    """
    Process slide content for AI consumption.
    """
    
    def __init__(self):
        self.client = genai.Client(api_key=config.GEMINI_API_KEY)
        self.model = config.STATIC_GEMINI_MODEL

    async def process_slides(self, file_path: Path) -> str:
        """
        Read slides.md and generate a static summary using Gemini Flash.
        
        Args:
            file_path: Path to the markdown slides file.
            
        Returns:
            A string containing the technical summary of the slides.
        """
        try:
            if not file_path.exists():
                logger.error(f"Slides file not found: {file_path}")
                return "Error: Slides file not found."

            content = file_path.read_text(encoding="utf-8")
            
            prompt = f"""
            Here is the markdown content of a presentation slide deck.
            Please analyze it and provide a concise technical summary of the key points covered in the slides.
            This summary will be used as context for an AI assistant to answer questions and generate summaries during the live presentation.
            
            Focus on:
            1. Key topics and concepts.
            2. Technical details and architecture.
            3. Main takeaways.
            
            Slides Content:
            {content}
            """
            
            logger.info("Generating static slide summary...")
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=prompt
            )
            
            if response.text:
                logger.info("Static slide summary generated successfully.")
                return response.text
            else:
                logger.warning("Empty response from Gemini for slide summary.")
                return "Error: Could not generate summary."
                
        except Exception as e:
            logger.error(f"Failed to process slides: {e}")
            return f"Error generating slide summary: {str(e)}"

    async def generate_presentation_summary(self, transcript: str, slide_context: str) -> str:
        """
        Generate a summary of the live presentation based on transcript and slides.
        """
        try:
            prompt = f"""
            You are a helpful presentation assistant. The user has asked for a summary of the presentation so far.
            
            CONTEXT:
            - Slide Content Summary: {slide_context}
            - Live Transcript (what the speaker said): {transcript}
            
            TASK:
            Generate a concise, bulleted summary of what has been discussed using HTML format.
            - Focus on the main points covered by the speaker.
            - Use the slide context to fill in details or clarify terms.
            - Format for a slide presentation:
                - Use `<ul>` and `<li>` tags for the list.
                - Use `<strong>` for key terms.
                - Do NOT use Markdown (no asterisks).
                - Do NOT wrap in ```html code blocks. Return raw HTML only.
            """
            
            logger.info("Generating live presentation summary...")
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=prompt
            )
            
            if response.text:
                logger.info("Live summary generated successfully.")
                # Clean up potential markdown code blocks
                clean_text = response.text.replace("```html", "").replace("```", "").strip()
                return clean_text
            else:
                return "Could not generate summary."
        except Exception as e:
            logger.error(f"Failed to generate live summary: {e}")
            return f"Error: {e}"
