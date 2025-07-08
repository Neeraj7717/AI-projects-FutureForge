import React from 'react';
import { Box, styled, Radio, FormControlLabel, RadioGroup } from '@mui/material';
import StepContainer, { H1, InstagramDivider } from './StepContainer';

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

const ShowAllText = styled(Box)({
  color: '#0095F6',
  fontSize: '14px',
  fontWeight: 600,
  marginTop: '4px',
  cursor: 'pointer',
  '&:hover': {
    textDecoration: 'underline',
  },
});

interface PostSelectionProps {
  selectedPost: 'specific' | 'any' | 'next';
  onSelectionChange: (selected: 'specific' | 'any' | 'next') => void;
  onShowAll: () => void;
}

const PostSelection: React.FC<PostSelectionProps> = ({
  selectedPost,
  onSelectionChange,
  onShowAll,
}) => {
  return (
    <StepContainer>
      <H1># When someone comments on</H1>
      <RadioGroup
        value={selectedPost}
        onChange={(e) => onSelectionChange(e.target.value as 'specific' | 'any' | 'next')}
      >
        <RadioOption
          value="specific"
          control={<Radio />}
          label={
            <Box>
              a specific post or reel
              <ShowAllText onClick={onShowAll}>Show All</ShowAllText>
            </Box>
          }
        />
        <RadioOption
          value="any"
          control={<Radio />}
          label="any post or reel"
        />
        <RadioOption
          value="next"
          control={<Radio />}
          label="next post or reel"
        />
      </RadioGroup>
      <InstagramDivider />
    </StepContainer>
  );
};

export default PostSelection; 