import React, { useState } from 'react';
import { Box, styled, Radio, FormControlLabel, RadioGroup, Chip, TextField } from '@mui/material';
import StepContainer, { H2, InstagramDivider } from './StepContainer';

const RadioOption = styled(FormControlLabel)({
  margin: '12px 0',
  alignItems: 'flex-start',
  '& .MuiFormControlLabel-label': {
    fontSize: '16px',
    color: '#262626',
    fontFamily: 'SF Pro Display, -apple-system, BlinkMacSystemFont, sans-serif',
    lineHeight: 1.4,
    marginLeft: '8px',
  },
  '& .MuiRadio-root': {
    color: '#DBDBDB',
    '&.Mui-checked': {
      color: '#0095F6',
    },
  },
});

const KeywordChip = styled(Chip)({
  backgroundColor: '#EFEFEF',
  borderRadius: '8px',
  fontSize: '14px',
  fontWeight: 500,
  color: '#262626',
  marginTop: '8px',
  cursor: 'pointer',
  '&:hover': {
    backgroundColor: '#E0E0E0',
  },
});

const HelperText = styled(Box)({
  fontSize: '14px',
  color: '#8E8E8E',
  marginTop: '8px',
  fontFamily: 'SF Pro Display, -apple-system, BlinkMacSystemFont, sans-serif',
});

const ExampleText = styled(Box)({
  fontSize: '14px',
  color: '#8E8E8E',
  fontStyle: 'italic',
  marginTop: '4px',
  fontFamily: 'SF Pro Display, -apple-system, BlinkMacSystemFont, sans-serif',
});

const KeywordInput = styled(TextField)({
  marginTop: '8px',
  '& .MuiOutlinedInput-root': {
    fontSize: '14px',
    '& fieldset': {
      border: 'none',
      borderBottom: '1px solid #DBDBDB',
      borderRadius: 0,
    },
    '&:hover fieldset': {
      borderBottom: '1px solid #262626',
    },
    '&.Mui-focused fieldset': {
      borderBottom: '2px solid #0095F6',
    },
  },
  '& .MuiInputBase-input': {
    padding: '8px 0',
  },
});

interface CommentTriggerProps {
  selectedTrigger: 'specific' | 'any';
  keywords: string[];
  onSelectionChange: (selected: 'specific' | 'any') => void;
  onKeywordsChange: (keywords: string[]) => void;
}

const CommentTrigger: React.FC<CommentTriggerProps> = ({
  selectedTrigger,
  keywords,
  onSelectionChange,
  onKeywordsChange,
}) => {
  const [editingKeyword, setEditingKeyword] = useState<string>('');
  const [editingIndex, setEditingIndex] = useState<number>(-1);

  const handleKeywordEdit = (index: number) => {
    setEditingKeyword(keywords[index]);
    setEditingIndex(index);
  };

  const handleKeywordSave = () => {
    if (editingIndex >= 0 && editingKeyword.trim()) {
      const newKeywords = [...keywords];
      newKeywords[editingIndex] = editingKeyword.trim();
      onKeywordsChange(newKeywords);
    }
    setEditingIndex(-1);
    setEditingKeyword('');
  };

  const handleKeywordDelete = (index: number) => {
    const newKeywords = keywords.filter((_, i) => i !== index);
    onKeywordsChange(newKeywords);
  };

  const handleAddKeyword = () => {
    if (editingKeyword.trim()) {
      onKeywordsChange([...keywords, editingKeyword.trim()]);
      setEditingKeyword('');
    }
  };

  return (
    <StepContainer>
      <H2>## And this comment has</H2>
      <RadioGroup
        value={selectedTrigger}
        onChange={(e) => onSelectionChange(e.target.value as 'specific' | 'any')}
      >
        <RadioOption
          value="specific"
          control={<Radio />}
          label={
            <Box>
              a specific word or words
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, marginTop: 1 }}>
                {keywords.map((keyword, index) => (
                  <KeywordChip
                    key={index}
                    label={`${keyword}: ${index + 1}`}
                    onClick={() => handleKeywordEdit(index)}
                    onDelete={() => handleKeywordDelete(index)}
                    deleteIcon={<Box sx={{ fontSize: '16px', marginRight: '4px' }}>×</Box>}
                  />
                ))}
                {editingIndex === -1 && (
                  <KeywordInput
                    placeholder="Add keyword..."
                    value={editingKeyword}
                    onChange={(e) => setEditingKeyword(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && handleAddKeyword()}
                    onBlur={handleAddKeyword}
                    size="small"
                  />
                )}
                {editingIndex >= 0 && (
                  <KeywordInput
                    value={editingKeyword}
                    onChange={(e) => setEditingKeyword(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && handleKeywordSave()}
                    onBlur={handleKeywordSave}
                    size="small"
                    autoFocus
                  />
                )}
              </Box>
              <HelperText>Use content to separate words</HelperText>
              <ExampleText>For example: (Price) (Link) (Shop)</ExampleText>
            </Box>
          }
        />
        <RadioOption
          value="any"
          control={<Radio />}
          label="any word"
        />
      </RadioGroup>
      <InstagramDivider />
    </StepContainer>
  );
};

export default CommentTrigger; 