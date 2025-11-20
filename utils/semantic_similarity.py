from transformers import AutoTokenizer, AutoModel
import torch
from sklearn.metrics.pairwise import cosine_similarity
import time  

class SentenceSimilarityCalculator:
    """
    Class to calculate the similarity between two sentences using BERT embeddings.
    """
    def __init__(self, model_name='sentence-transformers/bert-base-nli-mean-tokens'):
        """
        Initialize the SentenceSimilarityCalculator.

        Parameters:
        - model_name (str): The name of the pretrained model to use.
        """
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name)
        self.max_length = self.get_max_length()

    def get_max_length(self):
        """
        Get the maximum length supported by the tokenizer.

        Returns:
        - max_length (int or None): The maximum length, or None if not available.
        """
        if hasattr(self.tokenizer, "model_max_length"):
            return min(self.tokenizer.model_max_length, 512)  
        return None

    def calculate_bert_embeddings(self, sentences):
        """
        Calculate BERT embeddings for the input sentences.

        Parameters:
        - sentences (list of str): Input sentences to calculate embeddings for.

        Returns:
        - embeddings (torch.Tensor): Tensor containing the BERT embeddings for the input sentences.
        - duration (float): The execution time in seconds.
        """
        
        # Tokenize the sentences and prepare input tensors
        tokenized_sentences = self.tokenizer(
            sentences, 
            padding=True, 
            truncation=True if self.max_length else False,  
            max_length=self.max_length,
            return_tensors='pt'
        )
        
        # Calculate embeddings using the model
        with torch.no_grad():
            outputs = self.model(**tokenized_sentences)
        embeddings = outputs.last_hidden_state
        
        return embeddings

    def calculate_similarity(self, sentence1, sentence2):
        """
        Calculate the cosine similarity between two sentences.

        Parameters:
        - sentence1 (str): First sentence.
        - sentence2 (str): Second sentence.

        Returns:
        - similarity_score (float): Cosine similarity score between the two sentences.
        - duration (float): The execution time in seconds.
        """
        
        start_time = time.time()  # Start the timer

        # Calculate BERT embeddings for both sentences
        embedding1 = self.calculate_bert_embeddings([sentence1])
        embedding2 = self.calculate_bert_embeddings([sentence2])
        
        # Calculate mean-pooled embeddings
        mask1 = torch.ones_like(embedding1)
        mask1[torch.eq(embedding1, 0)] = 0
        summed1 = torch.sum(embedding1 * mask1, dim=1)
        mask_sum1 = torch.clamp(mask1.sum(1), min=1e-9)
        mean_pooled1 = summed1 / mask_sum1
        
        mask2 = torch.ones_like(embedding2)
        mask2[torch.eq(embedding2, 0)] = 0
        summed2 = torch.sum(embedding2 * mask2, dim=1)
        mask_sum2 = torch.clamp(mask2.sum(1), min=1e-9)
        mean_pooled2 = summed2 / mask_sum2
        
        # Calculate cosine similarity
        similarity_score = cosine_similarity(mean_pooled1.numpy(), mean_pooled2.numpy())
        
        end_time = time.time()  # End the timer
        execution_time = end_time - start_time  # Calculate the elapsed time
        duration = f"{execution_time:.4f}"  # Format the execution time to four decimal places
        
        return float(similarity_score[0][0]), float(duration)

if __name__ == "__main__":
    # Example usage
    sentence1 = ""
    sentence2 = ""

    # Create instance of SentenceSimilarityCalculator
    similarity_calculator = SentenceSimilarityCalculator()

    # Calculate similarity between sentences
    similarity_score, duration = similarity_calculator.calculate_similarity(sentence1, sentence2)
    print("Cosine Similarity:", similarity_score)