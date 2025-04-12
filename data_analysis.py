import json
import re
import logging
from pathlib import Path
from collections import Counter
import os

# Try to import optional dependencies
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    print("Pandas not available. Data analysis will be limited.")

try:
    import matplotlib.pyplot as plt
    import seaborn as sns
    PLOT_AVAILABLE = True
except ImportError:
    PLOT_AVAILABLE = False
    print("Matplotlib or Seaborn not available. Plotting will be disabled.")

try:
    import nltk
    from nltk.tokenize import word_tokenize
    from nltk.corpus import stopwords
    from nltk.probability import FreqDist
    NLTK_AVAILABLE = True
    # Download NLTK data
    nltk.download('punkt', quiet=True)
    nltk.download('stopwords', quiet=True)
except ImportError:
    NLTK_AVAILABLE = False
    print("NLTK not available. Text analysis will be limited.")

try:
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.cluster import KMeans
    from sklearn.decomposition import PCA
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    print("Scikit-learn not available. Clustering will be disabled.")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('data_analysis.log')
    ]
)

logger = logging.getLogger('data_analysis')

class USCDataAnalyzer:
    def __init__(self, processed_dir="processed", output_dir="analysis_results"):
        self.processed_dir = Path(processed_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        # Create directories for analysis outputs
        self.stats_dir = self.output_dir / "statistics"
        self.stats_dir.mkdir(exist_ok=True)

        self.plots_dir = self.output_dir / "plots"
        self.plots_dir.mkdir(exist_ok=True)

        self.text_analysis_dir = self.output_dir / "text_analysis"
        self.text_analysis_dir.mkdir(exist_ok=True)

        self.clustering_dir = self.output_dir / "clustering"
        self.clustering_dir.mkdir(exist_ok=True)

        # Set up stopwords if NLTK is available
        if NLTK_AVAILABLE:
            self.stop_words = set(stopwords.words('english'))
            self.stop_words.update(['shall', 'may', 'section', 'subsection', 'paragraph', 'title', 'chapter', 'united', 'states'])
        else:
            # Fallback stopwords
            self.stop_words = set(['the', 'and', 'a', 'to', 'of', 'in', 'for', 'on', 'with', 'by', 'at', 'from',
                                  'shall', 'may', 'section', 'subsection', 'paragraph', 'title', 'chapter', 'united', 'states'])

    def analyze_all_titles(self):
        """Analyze all titles"""
        # Get all JSON files in the processed directory
        json_files = list(self.processed_dir.glob("*.json"))

        logger.info(f"Found {len(json_files)} processed titles")

        # Load all titles
        titles_data = []
        for json_file in json_files:
            try:
                title_match = re.search(r'usc(\d+)\.json', json_file.name)
                if title_match:
                    title_num = int(title_match.group(1))

                    # Load the JSON data
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    titles_data.append({
                        'number': title_num,
                        'data': data
                    })
            except Exception as e:
                logger.error(f"Error loading {json_file.name}: {e}")

        # Sort titles by number
        titles_data.sort(key=lambda x: x['number'])

        logger.info(f"Loaded {len(titles_data)} titles")

        # Perform various analyses
        self.analyze_title_statistics(titles_data)
        self.analyze_text_complexity(titles_data)
        self.analyze_word_frequencies(titles_data)
        self.cluster_titles(titles_data)
        self.analyze_cross_references(titles_data)

        logger.info("Analysis complete")

    def analyze_title_statistics(self, titles_data):
        """Analyze basic statistics for each title"""
        logger.info("Analyzing title statistics...")

        # Create a list to store statistics
        stats = []

        for title in titles_data:
            title_num = title['number']
            data = title['data']

            # Get title name
            title_name = data['content']['title']['heading'] if 'content' in data and 'title' in data['content'] and 'heading' in data['content']['title'] else f"Title {title_num}"

            # Count chapters
            num_chapters = len(data['content'].get('chapters', []))

            # Count sections
            num_sections = 0
            for chapter in data['content'].get('chapters', []):
                num_sections += len(chapter.get('sections', []))

            # Count subsections
            num_subsections = 0
            for chapter in data['content'].get('chapters', []):
                for section in chapter.get('sections', []):
                    num_subsections += len(section.get('subsections', []))

            # Calculate total text length
            total_text = ""
            for chapter in data['content'].get('chapters', []):
                if 'content' in chapter:
                    total_text += chapter['content'] + " "

                for section in chapter.get('sections', []):
                    if 'content' in section:
                        total_text += section['content'] + " "

                    for subsection in section.get('subsections', []):
                        if 'content' in subsection:
                            total_text += subsection['content'] + " "

            text_length = len(total_text)
            word_count = len(total_text.split())

            # Add to statistics
            stats.append({
                'Title Number': title_num,
                'Title Name': title_name,
                'Chapters': num_chapters,
                'Sections': num_sections,
                'Subsections': num_subsections,
                'Text Length (chars)': text_length,
                'Word Count': word_count
            })

        # Save statistics to JSON if pandas is not available
        if not PANDAS_AVAILABLE:
            json_file = self.stats_dir / "title_statistics.json"
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(stats, f, indent=2)
            logger.info(f"Title statistics saved to {json_file}")
            return

        # Create DataFrame
        df = pd.DataFrame(stats)

        # Save statistics to CSV
        csv_file = self.stats_dir / "title_statistics.csv"
        df.to_csv(csv_file, index=False)
        logger.info(f"Title statistics saved to {csv_file}")

        # Skip visualizations if plotting is not available
        if not PLOT_AVAILABLE:
            logger.warning("Plotting is disabled due to missing dependencies")
            return

        try:
            # Create visualizations

            # 1. Bar chart of number of chapters per title
            plt.figure(figsize=(12, 6))
            sns.barplot(x='Title Number', y='Chapters', data=df)
            plt.title('Number of Chapters per Title')
            plt.xticks(rotation=90)
            plt.tight_layout()
            plt.savefig(self.plots_dir / "chapters_per_title.png")
            plt.close()

            # 2. Bar chart of number of sections per title
            plt.figure(figsize=(12, 6))
            sns.barplot(x='Title Number', y='Sections', data=df)
            plt.title('Number of Sections per Title')
            plt.xticks(rotation=90)
            plt.tight_layout()
            plt.savefig(self.plots_dir / "sections_per_title.png")
            plt.close()

            # 3. Bar chart of word count per title
            plt.figure(figsize=(12, 6))
            sns.barplot(x='Title Number', y='Word Count', data=df)
            plt.title('Word Count per Title')
            plt.xticks(rotation=90)
            plt.tight_layout()
            plt.savefig(self.plots_dir / "word_count_per_title.png")
            plt.close()

            # 4. Scatter plot of sections vs. word count
            plt.figure(figsize=(10, 6))
            sns.scatterplot(x='Sections', y='Word Count', hue='Title Number', data=df, palette='viridis')
            plt.title('Sections vs. Word Count')
            plt.tight_layout()
            plt.savefig(self.plots_dir / "sections_vs_word_count.png")
            plt.close()

            logger.info("Created visualizations for title statistics")
        except Exception as e:
            logger.error(f"Error creating visualizations: {e}")

    def analyze_text_complexity(self, titles_data):
        """Analyze text complexity for each title"""
        logger.info("Analyzing text complexity...")

        # Create a DataFrame to store complexity metrics
        complexity = []

        for title in titles_data:
            title_num = title['number']
            data = title['data']

            # Get title name
            title_name = data['content']['title']['heading'] if 'content' in data and 'title' in data['content'] and 'heading' in data['content']['title'] else f"Title {title_num}"

            # Extract all text
            all_text = ""
            for chapter in data['content'].get('chapters', []):
                if 'content' in chapter:
                    all_text += chapter['content'] + " "

                for section in chapter.get('sections', []):
                    if 'content' in section:
                        all_text += section['content'] + " "

            # Skip if no text
            if not all_text:
                continue

            # Tokenize text
            tokens = word_tokenize(all_text.lower())

            # Remove stopwords
            filtered_tokens = [word for word in tokens if word.isalpha() and word not in self.stop_words]

            # Calculate metrics
            total_words = len(filtered_tokens)
            unique_words = len(set(filtered_tokens))

            # Calculate average word length
            avg_word_length = sum(len(word) for word in filtered_tokens) / total_words if total_words > 0 else 0

            # Calculate average sentence length
            sentences = nltk.sent_tokenize(all_text)
            avg_sentence_length = total_words / len(sentences) if len(sentences) > 0 else 0

            # Calculate lexical diversity (unique words / total words)
            lexical_diversity = unique_words / total_words if total_words > 0 else 0

            # Add to complexity metrics
            complexity.append({
                'Title Number': title_num,
                'Title Name': title_name,
                'Total Words': total_words,
                'Unique Words': unique_words,
                'Average Word Length': avg_word_length,
                'Average Sentence Length': avg_sentence_length,
                'Lexical Diversity': lexical_diversity
            })

        # Create DataFrame
        df = pd.DataFrame(complexity)

        # Save complexity metrics to CSV
        csv_file = self.text_analysis_dir / "text_complexity.csv"
        df.to_csv(csv_file, index=False)

        # Create visualizations

        # 1. Bar chart of lexical diversity per title
        plt.figure(figsize=(12, 6))
        sns.barplot(x='Title Number', y='Lexical Diversity', data=df)
        plt.title('Lexical Diversity per Title')
        plt.xticks(rotation=90)
        plt.tight_layout()
        plt.savefig(self.text_analysis_dir / "lexical_diversity.png")
        plt.close()

        # 2. Bar chart of average sentence length per title
        plt.figure(figsize=(12, 6))
        sns.barplot(x='Title Number', y='Average Sentence Length', data=df)
        plt.title('Average Sentence Length per Title')
        plt.xticks(rotation=90)
        plt.tight_layout()
        plt.savefig(self.text_analysis_dir / "avg_sentence_length.png")
        plt.close()

        # 3. Scatter plot of lexical diversity vs. average sentence length
        plt.figure(figsize=(10, 6))
        sns.scatterplot(x='Lexical Diversity', y='Average Sentence Length', hue='Title Number', data=df, palette='viridis')
        plt.title('Lexical Diversity vs. Average Sentence Length')
        plt.tight_layout()
        plt.savefig(self.text_analysis_dir / "diversity_vs_sentence_length.png")
        plt.close()

        logger.info(f"Text complexity metrics saved to {csv_file}")

    def analyze_word_frequencies(self, titles_data):
        """Analyze word frequencies for each title"""
        logger.info("Analyzing word frequencies...")

        # Analyze overall word frequencies
        all_words = []

        for title in titles_data:
            title_num = title['number']
            data = title['data']

            # Extract all text
            all_text = ""
            for chapter in data['content'].get('chapters', []):
                if 'content' in chapter:
                    all_text += chapter['content'] + " "

                for section in chapter.get('sections', []):
                    if 'content' in section:
                        all_text += section['content'] + " "

            # Tokenize text
            tokens = word_tokenize(all_text.lower())

            # Remove stopwords and non-alphabetic tokens
            filtered_tokens = [word for word in tokens if word.isalpha() and word not in self.stop_words]

            all_words.extend(filtered_tokens)

            # Analyze word frequencies for this title
            if filtered_tokens:
                # Get frequency distribution
                fdist = FreqDist(filtered_tokens)

                # Get top 50 words
                top_words = fdist.most_common(50)

                # Create DataFrame
                df = pd.DataFrame(top_words, columns=['Word', 'Frequency'])

                # Save to CSV
                csv_file = self.text_analysis_dir / f"title{title_num}_word_frequencies.csv"
                df.to_csv(csv_file, index=False)

                # Create word frequency plot
                plt.figure(figsize=(12, 8))
                sns.barplot(x='Frequency', y='Word', data=df.head(20))
                plt.title(f'Top 20 Words in Title {title_num}')
                plt.tight_layout()
                plt.savefig(self.text_analysis_dir / f"title{title_num}_word_frequencies.png")
                plt.close()

        # Analyze overall word frequencies
        if all_words:
            # Get frequency distribution
            fdist = FreqDist(all_words)

            # Get top 100 words
            top_words = fdist.most_common(100)

            # Create DataFrame
            df = pd.DataFrame(top_words, columns=['Word', 'Frequency'])

            # Save to CSV
            csv_file = self.text_analysis_dir / "overall_word_frequencies.csv"
            df.to_csv(csv_file, index=False)

            # Create word frequency plot
            plt.figure(figsize=(12, 8))
            sns.barplot(x='Frequency', y='Word', data=df.head(30))
            plt.title('Top 30 Words Across All Titles')
            plt.tight_layout()
            plt.savefig(self.text_analysis_dir / "overall_word_frequencies.png")
            plt.close()

            logger.info(f"Overall word frequencies saved to {csv_file}")

    def cluster_titles(self, titles_data):
        """Cluster titles based on content similarity"""
        logger.info("Clustering titles based on content similarity...")

        # Skip if scikit-learn is not available
        if not SKLEARN_AVAILABLE:
            logger.warning("Clustering disabled due to missing dependencies")
            return

        # Skip if pandas is not available
        if not PANDAS_AVAILABLE:
            logger.warning("Clustering disabled due to missing pandas")
            return

        # Skip if plotting is not available
        if not PLOT_AVAILABLE:
            logger.warning("Clustering visualization disabled due to missing plotting dependencies")
            # We can still do clustering without visualization

        # Extract text and title numbers
        texts = []
        title_nums = []

        for title in titles_data:
            title_num = title['number']
            data = title['data']

            # Extract all text
            all_text = ""
            for chapter in data['content'].get('chapters', []):
                if 'content' in chapter:
                    all_text += chapter['content'] + " "

                for section in chapter.get('sections', []):
                    if 'content' in section:
                        all_text += section['content'] + " "

            # Skip if no text
            if not all_text:
                continue

            texts.append(all_text)
            title_nums.append(title_num)

        # Skip if not enough titles
        if len(texts) < 2:
            logger.warning("Not enough titles with content for clustering")
            return

        try:
            # Create TF-IDF vectors
            vectorizer = TfidfVectorizer(max_features=1000, stop_words=self.stop_words)
            X = vectorizer.fit_transform(texts)

            # Choose number of clusters
            n_clusters = min(5, len(texts) - 1)  # Use at most 5 clusters, but ensure it's less than the number of samples

            # Perform K-means clustering
            kmeans = KMeans(n_clusters=n_clusters, random_state=42)
            clusters = kmeans.fit_predict(X)

            # Create DataFrame with clustering results
            df = pd.DataFrame({
                'Title Number': title_nums,
                'Cluster': clusters
            })

            # Save clustering results to CSV
            csv_file = self.clustering_dir / "title_clusters.csv"
            df.to_csv(csv_file, index=False)
            logger.info(f"Title clustering results saved to {csv_file}")

            # Skip visualization if plotting is not available
            if not PLOT_AVAILABLE:
                return

            # Determine optimal number of clusters using the elbow method
            distortions = []
            K = range(2, min(10, len(texts)))
            for k in K:
                kmeans = KMeans(n_clusters=k, random_state=42)
                kmeans.fit(X)
                distortions.append(kmeans.inertia_)

            # Plot elbow curve
            plt.figure(figsize=(10, 6))
            plt.plot(K, distortions, 'bx-')
            plt.xlabel('Number of clusters')
            plt.ylabel('Distortion')
            plt.title('Elbow Method For Optimal k')
            plt.savefig(self.clustering_dir / "elbow_curve.png")
            plt.close()

            # Reduce dimensionality for visualization
            pca = PCA(n_components=2)
            X_pca = pca.fit_transform(X.toarray())

            # Create DataFrame for plotting
            plot_df = pd.DataFrame({
                'Title Number': title_nums,
                'Cluster': clusters,
                'PCA1': X_pca[:, 0],
                'PCA2': X_pca[:, 1]
            })

            # Plot clusters
            plt.figure(figsize=(12, 8))
            sns.scatterplot(x='PCA1', y='PCA2', hue='Cluster', data=plot_df, palette='viridis')

            # Add title numbers as labels
            for _, row in plot_df.iterrows():
                plt.text(row['PCA1'], row['PCA2'], str(int(row['Title Number'])))

            plt.title('Title Clusters Based on Content Similarity')
            plt.savefig(self.clustering_dir / "title_clusters.png")
            plt.close()

            logger.info("Created visualizations for title clustering")
        except Exception as e:
            logger.error(f"Error clustering titles: {e}")

    def analyze_cross_references(self, titles_data):
        """Analyze cross-references between titles"""
        logger.info("Analyzing cross-references between titles...")

        # Check if advanced processing has been done
        advanced_dir = Path("advanced_processed")
        cross_refs_dir = advanced_dir / "cross_references"

        if not cross_refs_dir.exists():
            logger.warning("Advanced processing directory not found. Run advanced_processor.py first.")
            return

        # Load cross-references for all titles
        all_refs = []

        for title in titles_data:
            title_num = title['number']

            # Load cross-references
            cross_refs_file = cross_refs_dir / f"title{title_num}_cross_refs.json"
            if cross_refs_file.exists():
                try:
                    with open(cross_refs_file, 'r', encoding='utf-8') as f:
                        refs = json.load(f)

                    all_refs.extend(refs)
                except Exception as e:
                    logger.error(f"Error loading cross-references for Title {title_num}: {e}")

        # Skip if no cross-references
        if not all_refs:
            logger.warning("No cross-references found")
            return

        # Create DataFrame
        df = pd.DataFrame(all_refs)

        # Save to CSV
        csv_file = self.stats_dir / "cross_references.csv"
        df.to_csv(csv_file, index=False)

        # Create cross-reference matrix
        title_nums = sorted(list(set(df['source_title'].tolist() + df['referenced_title'].tolist())))
        matrix = np.zeros((len(title_nums), len(title_nums)))

        for _, row in df.iterrows():
            source_idx = title_nums.index(row['source_title'])
            target_idx = title_nums.index(row['referenced_title'])
            matrix[source_idx, target_idx] += 1

        # Create DataFrame for the matrix
        matrix_df = pd.DataFrame(matrix, index=title_nums, columns=title_nums)

        # Save matrix to CSV
        matrix_csv = self.stats_dir / "cross_reference_matrix.csv"
        matrix_df.to_csv(matrix_csv)

        # Create heatmap
        plt.figure(figsize=(12, 10))
        sns.heatmap(matrix_df, annot=True, cmap='viridis', fmt='.0f')
        plt.title('Cross-references Between Titles')
        plt.xlabel('Referenced Title')
        plt.ylabel('Source Title')
        plt.savefig(self.plots_dir / "cross_reference_heatmap.png")
        plt.close()

        # Create bar chart of most referenced titles
        ref_counts = df['referenced_title'].value_counts().reset_index()
        ref_counts.columns = ['Title', 'References']

        plt.figure(figsize=(12, 6))
        sns.barplot(x='Title', y='References', data=ref_counts.head(20))
        plt.title('Most Referenced Titles')
        plt.xticks(rotation=90)
        plt.tight_layout()
        plt.savefig(self.plots_dir / "most_referenced_titles.png")
        plt.close()

        # Create bar chart of titles with most outgoing references
        source_counts = df['source_title'].value_counts().reset_index()
        source_counts.columns = ['Title', 'References']

        plt.figure(figsize=(12, 6))
        sns.barplot(x='Title', y='References', data=source_counts.head(20))
        plt.title('Titles with Most Outgoing References')
        plt.xticks(rotation=90)
        plt.tight_layout()
        plt.savefig(self.plots_dir / "most_outgoing_references.png")
        plt.close()

        logger.info(f"Cross-reference analysis saved to {csv_file}")

if __name__ == "__main__":
    analyzer = USCDataAnalyzer()
    analyzer.analyze_all_titles()
