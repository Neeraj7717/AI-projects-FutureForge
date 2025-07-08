import React, { useState } from 'react';
import { Box, styled, TextField, Button, Collapse, IconButton } from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import StepContainer, { H2 } from './StepContainer';

const DMSection = styled(Box)({
  marginBottom: '24px',
});

const SectionTitle = styled(Box)({
  fontSize: '16px',
  fontWeight: 600,
  color: '#262626',
  marginBottom: '12px',
  fontFamily: 'SF Pro Display, -apple-system, BlinkMacSystemFont, sans-serif',
});

const DMPreview = styled(Box)({
  backgroundColor: '#F8F9FA',
  border: '1px solid #DBDBDB',
  borderRadius: '8px',
  padding: '16px',
  fontSize: '14px',
  lineHeight: 1.5,
  color: '#262626',
  fontFamily: 'SF Pro Display, -apple-system, BlinkMacSystemFont, sans-serif',
  whiteSpace: 'pre-wrap',
  marginBottom: '12px',
});

const AddLinkButton = styled(Button)({
  color: '#0095F6',
  fontSize: '14px',
  fontWeight: 600,
  textTransform: 'none',
  padding: '8px 0',
  minWidth: 'auto',
  '&:hover': {
    backgroundColor: 'transparent',
    textDecoration: 'underline',
  },
});

const CollapsibleSection = styled(Box)({
  borderTop: '1px solid #DBDBDB',
  paddingTop: '16px',
});

const CollapsibleHeader = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  cursor: 'pointer',
  padding: '8px 0',
});

const CollapsibleTitle = styled(Box)({
  fontSize: '14px',
  fontWeight: 600,
  color: '#262626',
  fontFamily: 'SF Pro Display, -apple-system, BlinkMacSystemFont, sans-serif',
});

const CollapsibleContent = styled(Box)({
  fontSize: '14px',
  color: '#8E8E8E',
  lineHeight: 1.5,
  padding: '8px 0',
  fontFamily: 'SF Pro Display, -apple-system, BlinkMacSystemFont, sans-serif',
});

const MessageTextarea = styled(TextField)({
  marginBottom: '16px',
  '& .MuiOutlinedInput-root': {
    fontSize: '14px',
    fontFamily: 'SF Pro Display, -apple-system, BlinkMacSystemFont, sans-serif',
    '& fieldset': {
      border: '1px solid #DBDBDB',
      borderRadius: '8px',
    },
    '&:hover fieldset': {
      borderColor: '#262626',
    },
    '&.Mui-focused fieldset': {
      borderColor: '#0095F6',
    },
  },
  '& .MuiInputBase-input': {
    padding: '12px',
    lineHeight: 1.5,
  },
});

const CharacterCount = styled(Box)({
  fontSize: '12px',
  color: '#8E8E8E',
  textAlign: 'right',
  marginTop: '4px',
  fontFamily: 'SF Pro Display, -apple-system, BlinkMacSystemFont, sans-serif',
});

interface DMConfigurationProps {
  dmMessage: string;
  onMessageChange: (message: string) => void;
}

const DMConfiguration: React.FC<DMConfigurationProps> = ({
  dmMessage,
  onMessageChange,
}) => {
  const [expanded, setExpanded] = useState(false);

  const handleAddLink = () => {
    // Handle link insertion
    console.log('Add link functionality');
  };

  return (
    <StepContainer>
      <H2>## They will get</H2>
      
      <DMSection>
        <SectionTitle>an opening DM</SectionTitle>
        <DMPreview>{dmMessage}</DMPreview>
        <AddLinkButton onClick={handleAddLink}>Add A Link</AddLinkButton>
      </DMSection>

      <CollapsibleSection>
        <CollapsibleHeader onClick={() => setExpanded(!expanded)}>
          <CollapsibleTitle>Why does an Opening DM matter?</CollapsibleTitle>
          <IconButton size="small">
            {expanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
          </IconButton>
        </CollapsibleHeader>
        <Collapse in={expanded}>
          <CollapsibleContent>
            An opening DM is the first message someone receives when they trigger your workflow. 
            It's your chance to make a great first impression and guide them toward your goal. 
            Keep it friendly, clear, and actionable.
          </CollapsibleContent>
        </Collapse>
      </CollapsibleSection>

      <Box sx={{ marginTop: '24px' }}>
        <MessageTextarea
          fullWidth
          multiline
          rows={6}
          placeholder="Type your opening DM message here..."
          value={dmMessage}
          onChange={(e) => onMessageChange(e.target.value)}
          variant="outlined"
        />
        <CharacterCount>
          {dmMessage.length} characters
        </CharacterCount>
      </Box>
    </StepContainer>
  );
};

export default DMConfiguration; 