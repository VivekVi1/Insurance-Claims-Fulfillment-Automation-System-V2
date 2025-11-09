# Prompts Folder Documentation

This folder contains all system prompts, email templates, and configuration files used by the Insurance Claims Processing System.

## 📁 File Structure

### **System Prompts**
- `fulfillment_system_prompt.txt` - LLM system prompt for fulfillment assessment
- `fulfillment_requirements.txt` - Detailed requirements documentation

### **Email Templates**
- `user_not_found_email.txt` - Email template for unregistered users
- `user_not_found_fallback.txt` - Fallback template for unregistered users (if main template fails)
- `fulfillment_pending_email.txt` - Email template for pending fulfillment requests

## 🔧 How It Works

The system automatically loads prompts from these files at runtime:

1. **Fulfillment Processor** (`fulfillment_processor.py`) reads:
   - `fulfillment_system_prompt.txt` for LLM instructions
   - `fulfillment_pending_email.txt` as fallback email template

2. **Mail Monitor** (`mail_monitor.py`) reads:
   - `user_not_found_email.txt` for rejection emails
   - `user_not_found_fallback.txt` as backup if main template fails

## 📝 Template Variables

Email templates support variable substitution:

### **user_not_found_email.txt & user_not_found_fallback.txt**
- `{claim_id}` - Unique claim reference ID
- `{user_email}` - Customer's email address

### **fulfillment_pending_email.txt**
- `{satisfied_items}` - List of requirements that have been satisfied
- `{missing_items}` - List of missing fulfillment items

## ✏️ Editing Prompts

To modify system behavior:

1. **Update LLM Instructions**: Edit `fulfillment_system_prompt.txt`
2. **Change Email Content**: Edit email template files
3. **Update Requirements**: Modify `fulfillment_requirements.txt`
4. **Restart Services**: Changes take effect on next restart

## 🔄 Benefits

- **Separation of Concerns**: Prompts separated from code
- **Easy Customization**: Modify prompts without code changes
- **Version Control**: Track prompt changes in git
- **Multi-language Support**: Easy to add translations
- **A/B Testing**: Swap prompt files for testing
- **Fallback Support**: Multiple template layers for reliability

## 📋 Example Usage

```python
# In your code
prompt_content = self.load_prompt_file('fulfillment_system_prompt.txt')
system_prompt = SystemMessage(content=prompt_content)
```

## 🚨 Important Notes

- Keep file encoding as UTF-8
- Test prompts after changes
- Backup original prompts before editing
- Use meaningful filenames for new prompts
- Fallback templates ensure system reliability 