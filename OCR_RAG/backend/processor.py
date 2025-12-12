import os
import glob
from pdf2image import convert_from_path
import tempfile
import shutil
import asyncio
from .ocr import OCRClient
from .embedding import EmbeddingClient
from .vector_store import VectorStore

class DataProcessor:
    def __init__(self):
        self.ocr_client = OCRClient()
        self.embed_client = EmbeddingClient()
        self.vector_store = VectorStore()

    async def process_file(self, file_path, person_name="unknown"):
        """
        Process a single file: Extract text -> Embed -> Store (Async)
        """
        print(f"Processing single file {file_path} for person {person_name}")
        texts = await self._extract_text_async(file_path)
        
        # If OCR returned empty, check if we should still return True (processed but empty) or False (failed)
        # Usually False so we know it didn't add anything.
        if not texts:
            print(f"No text extracted from {file_path}")
            return False

        new_embeddings = []
        new_metas = []

        # Create tasks for embeddings
        embedding_tasks = []
        valid_texts = []
        
        for text in texts:
            # Filter out empty or very short garbage
            if not text or len(text.strip()) < 5:
                continue
            valid_texts.append(text)
            embedding_tasks.append(self.embed_client.get_embedding(text))
        
        if not embedding_tasks:
            print(f"No valid text to embed for {file_path}")
            return False

        # Run embedding tasks concurrently
        embeddings = await asyncio.gather(*embedding_tasks)
        
        for text, embedding in zip(valid_texts, embeddings):
            if embedding:
                new_embeddings.append(embedding)
                new_metas.append({
                    "text": text,
                    "source": file_path,
                    "person": person_name,
                    "filename": os.path.basename(file_path)
                })
        
        if new_embeddings:
            # Vector store addition is likely synchronous (FAISS/local file write), 
            # so we might want to run it in a thread if it's slow, but usually it's fast enough for small batches.
            # If needed: await asyncio.to_thread(self.vector_store.add_documents, new_embeddings, new_metas)
            self.vector_store.add_documents(new_embeddings, new_metas)
            self.vector_store.save() # Force explicit save to disk
            print(f"Successfully indexed {len(new_embeddings)} chunks for {file_path}")
        else:
            print(f"Embeddings failed for {file_path}")
        
        return len(new_embeddings) > 0

    async def process_directory(self, root_path, progress_callback=None):
        """
        Walks through the directory. (Async version)
        Structure assumed: root_path/person_name/file
        """
        if not os.path.exists(root_path):
            return "Path does not exist."

        # 1. Collect all files first
        all_files = []
        for root, dirs, files in os.walk(root_path):
            for file in files:
                if file.lower().endswith(('.pdf', '.png', '.jpg', '.jpeg')):
                    all_files.append(os.path.join(root, file))

        total_files = len(all_files)
        processed_count = 0
        
        # 2. Process concurrently (with semaphore to limit concurrency)
        semaphore = asyncio.Semaphore(5) # Limit to 5 concurrent file processings

        async def process_with_limit(file_path):
            nonlocal processed_count
            async with semaphore:
                # Determine person name
                rel_path = os.path.relpath(file_path, root_path)
                # rel_path is like "person_name/file.jpg" or "file.jpg"
                parts = rel_path.split(os.sep)
                if len(parts) > 1:
                    person_name = parts[0]
                else:
                    # Root folder case
                    person_name = os.path.basename(os.path.normpath(root_path))
                
                if progress_callback:
                    # Note: callback needs to be thread-safe or handled carefully if UI update
                    # For CLI print it's fine.
                    pass

                await self.process_file(file_path, person_name)
                processed_count += 1
                if progress_callback:
                     progress_callback(processed_count, total_files, f"Processed {os.path.basename(file_path)}")

        tasks = [process_with_limit(f) for f in all_files]
        await asyncio.gather(*tasks)

        if progress_callback:
            progress_callback(total_files, total_files, "Done!")
        return f"Processed {processed_count} files."

    async def _extract_text_async(self, file_path):
        ext = os.path.splitext(file_path)[1].lower()
        texts = []

        if ext == '.pdf':
            try:
                # Use a temp directory that we manually clean up AFTER OCR is done
                temp_dir = tempfile.mkdtemp()
                
                try:
                    def process_pdf_sync():
                        images = convert_from_path(file_path, output_folder=temp_dir)
                        image_paths = []
                        for i, image in enumerate(images):
                            image_path = os.path.join(temp_dir, f"page_{i}.jpg")
                            image.save(image_path, 'JPEG')
                            image_paths.append(image_path)
                        return image_paths
                    
                    image_paths = await asyncio.to_thread(process_pdf_sync)
                    
                    # Now OCR images concurrently
                    ocr_tasks = [self.ocr_client.get_text(img_path) for img_path in image_paths]
                    texts = await asyncio.gather(*ocr_tasks)
                    
                finally:
                    # Cleanup
                    shutil.rmtree(temp_dir, ignore_errors=True)
                
            except Exception as e:
                print(f"Error converting PDF {file_path}: {e}")
        else:
            # Add retry logic for connection errors
            for attempt in range(3):
                try:
                    text = await self.ocr_client.get_text(file_path)
                    if text:
                        texts.append(text)
                    break
                except Exception as e:
                    if "Connection error" in str(e) or "connection" in str(e).lower():
                        if attempt < 2:
                            await asyncio.sleep(1 * (attempt + 1))
                            continue
                    print(f"OCR Failed for {file_path}: {e}")
                    break
            
        return texts
