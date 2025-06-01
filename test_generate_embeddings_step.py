from unittest.mock import patch, MagicMock
from video_ingest_tool.steps.storage.embeddings import generate_embeddings_step

def test_generate_embeddings_step():
    data = {'clip_id': 1, 'model': {'some': 'data'}, 'ai_thumbnail_metadata': []}
    fake_metadata = {'summary_tokens': 10, 'keyword_tokens': 5, 'summary_truncation': 'none', 'keyword_truncation': 'none'}
    fake_embeddings = ([0.1, 0.2], [0.3, 0.4])
    fake_auth_manager = MagicMock()
    fake_auth_manager.get_current_session.return_value = True
    with patch('video_ingest_tool.auth.AuthManager', return_value=fake_auth_manager):
        with patch('video_ingest_tool.embeddings.prepare_embedding_content', return_value=('summary', 'keywords', fake_metadata)):
            with patch('video_ingest_tool.embeddings.generate_embeddings', return_value=fake_embeddings):
                with patch('video_ingest_tool.embeddings_image.batch_generate_thumbnail_embeddings', return_value={}):
                    with patch('video_ingest_tool.embeddings.store_embeddings') as mock_store:
                        result = generate_embeddings_step.fn(data)
                        assert result['embeddings_generated'] is True
                        assert result['clip_id'] == 1
                        assert result['summary_tokens'] == 10
                        assert result['keyword_tokens'] == 5 