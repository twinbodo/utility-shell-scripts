-- =========================================================
-- Universal Screen Wrapper (Updated API)
-- Jumps to the next screen from ANY edge, ignoring macOS layout
-- =========================================================

local function checkCursorWrap()
    -- Only run if multiple monitors are connected
    local screens = hs.screen.allScreens()
    if #screens < 2 then return end 

    -- Get position using the new API
    local pos = hs.mouse.absolutePosition()
    local screen = hs.mouse.getCurrentScreen()
    local nextScreen = screen:next()
    
    -- Get the physical boundaries of the current and next screen
    local f = screen:fullFrame()
    local nf = nextScreen:fullFrame()
    
    -- Threshold is how close to the edge triggers the warp
    -- Offset prevents the mouse from instantly bouncing back
    local threshold = 2
    local offset = 25 
    
    -- Calculate relative position so the mouse stays at a similar height/width on the new screen
    local relY = (pos.y - f.y) / f.h
    local mappedY = nf.y + (relY * nf.h)
    
    local relX = (pos.x - f.x) / f.w
    local mappedX = nf.x + (relX * nf.w)

    -- 1. Hit LEFT edge -> Teleport to RIGHT edge of next screen
    if pos.x <= f.x + threshold then
        -- Set position using the new API
        hs.mouse.absolutePosition({x = nf.x + nf.w - offset, y = mappedY})
        
    -- 2. Hit RIGHT edge -> Teleport to LEFT edge of next screen
    elseif pos.x >= (f.x + f.w) - threshold - 1 then
        hs.mouse.absolutePosition({x = nf.x + offset, y = mappedY})
        
    -- 3. Hit TOP edge -> Teleport to BOTTOM edge of next screen
    elseif pos.y <= f.y + threshold then
        hs.mouse.absolutePosition({x = mappedX, y = nf.y + nf.h - offset})
        
    -- 4. Hit BOTTOM edge -> Teleport to TOP edge of next screen
    elseif pos.y >= (f.y + f.h) - threshold - 1 then
        hs.mouse.absolutePosition({x = mappedX, y = nf.y + offset})
    end
end

-- Clear the old timer if reloading
if wrapTimer then wrapTimer:stop() end

-- Run the check silently in the background
wrapTimer = hs.timer.doEvery(0.05, checkCursorWrap)

hs.alert.show("Universal Screen Wrap Active!")